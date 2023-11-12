import pandas as pd
import numpy as np

df = pd.read_csv("customerData.csv")

# Remove duplicate rows and save to new csv
df = df.drop_duplicates()

# Choose a specific customer by ID
customerID = 25
df = df.loc[df['customerID'] == customerID]

# Sort csv by date and time
df['Formatted_DateTime'] = pd.to_datetime(df['Date_UTC'])
df = df.sort_values(by='Formatted_DateTime')

batteryEfficiency = 0.92

newNumberOfPanels = 9
numberOfBatteries = 1

batteryCapacity = numberOfBatteries * 6   # 6 kWh per battery

costOfPanels = newNumberOfPanels * 80
costOfBatteries = numberOfBatteries * 200

# Column F - PV power after scaling factor
df['pvPowerAfterScaling'] = (df['pv_totalPower_kW'] * newNumberOfPanels) / df['NumberOfPanels']

# Column J - Price before solar
df['priceBeforeSolar'] = df['price_gridImport_NZDperkWh'] * df['load_power_kW']/4

# Column K - Renewable energy to load before solar
df['energy2loadPreSolar'] = df['grid_renewableFraction_pct']*df['load_power_kW']/4

# Column L - Power supplied to load
df['pvSuppliedToLoad'] = df[['pvPowerAfterScaling', 'load_power_kW']].min(axis=1)

# Column M - Battery mode
df['batteryMode'] = 1

# Column N - Power into battery
df['batteryInput'] = 0

# Column O - Power out of battery
df['batteryOutput'] = 0

# Column Q - Charge from solar TODO need to use previous storedBatteryEnergy
df['storedBatteryEnergy'] = 0
df['chargeInFromSolar'] = df.apply(lambda x: (min(max(x['pvPowerAfterScaling'] - x['load_power_kW'], 0), batteryCapacity - x['storedBatteryEnergy'])) if x['batteryMode'] == 1 else 0, axis = 1)

# Column R - Charge from grid
df['chargeInFromGrid'] = df.apply(lambda x: min(x['batteryInput'], batteryCapacity-x['storedBatteryEnergy']) if x['batteryMode'] == 2 else 0, axis = 1)

# Column P - Battery charge incrase
df['batteryChargeIncrease'] = df['chargeInFromSolar'] + df['chargeInFromGrid']

# Column T - Discharge to load
df['dischargeToLoad'] = df.apply(lambda x: min(max(x['load_power_kW'] - x['pvPowerAfterScaling'], 0), x['storedBatteryEnergy']*np.sqrt(batteryEfficiency) if x['batteryMode'] == 1 else 0), axis = 1)

# Column U - Discharge to grid
df['dischargeToGrid'] = ((df['batteryOutput'] 
                           if df['batteryOutput'] < df['storedBatteryEnergy'] 
                           else df['storedBatteryEnergy'])/np.sqrt(batteryCapacity) 
                           if df['batteryMode'] is 2 else 0)

# Column S - Battery discharge
df['batteryChargeDecrease'] = df['dischargeToLoad'] + df['dischargeToGrid']

df['chargeAmount'] = df['batteryChargeIncrease'] - df['batteryChargeDecrease']

# Column V - Battery state of charge in kWh TODO something is wrong here!!
df['storedBatteryEnergy'] = df['chargeAmount'].cumsum().apply(lambda x: min(x, 6))
#df['storedBatteryEnergy'] = df['storedBatteryEnergy'].apply(lambda x: min(x, 6))  #df['storedBatteryEnergy'].clip(upper=6)

# Column W - Battery SOC%
df['batterySOC'] =  df['storedBatteryEnergy']/batteryCapacity

# Column X - New grid consumption
df['gridConsumption'] = df['load_power_kW'] - df['pvSuppliedToLoad'] - df['pvPowerAfterScaling'] + df['batteryChargeIncrease'] - df['batteryChargeDecrease']

# Column Y - Electricity cost post solar
df['costPostSolar'] = df.apply(lambda x: x['load_power_kW'] * (x['gridConsumption'] if x['gridConsumption'] > 0 else 0) / 4, axis=1)

# Column Z - Renewable energy to load post solar
df['renewableEnergyPostSolar'] = df.apply(lambda x: (x['grid_renewableFraction_pct'] * (x['gridConsumption'] if x['gridConsumption'] > 0 else 0) + x['pvSuppliedToLoad'] + x['chargeInFromSolar'])/4, axis=1)

# Column AB - Export income
df['exportIncome'] = df.apply(lambda x: (abs(x['gridConsumption'] if x['gridConsumption'] < 0 else 0))*x['price_gridExport_NZDperkWh']/4,axis=1)

# Adds column to DataFrame with cost for each 15 minute interval
df['cost_for_15m'] = df['price_gridImport_NZDperkWh'] * ((df['load_power_kW'] - (df['pv_totalPower_kW'] * newNumberOfPanels / df['NumberOfPanels'])) / 4)

# Makes negative costs equal 0
hasExcessPower = (df['load_power_kW'] - (df['pv_totalPower_kW'] * newNumberOfPanels / df['NumberOfPanels'])) < 0
df.loc[hasExcessPower, 'cost_for_15m'] = 0

# Creates export income column and sets all values to zero
df['export_income'] = 0

# For intervals where energy exported, calculates export income 
df.loc[hasExcessPower, 'export_income'] = (((df['pv_totalPower_kW'] * newNumberOfPanels / df['NumberOfPanels']) - df['load_power_kW']) / 4) * df['price_gridExport_NZDperkWh']

# For each 15 minute interval, calculates energy generated by solar panels
df['solar_energy_for_15m'] = df.apply(lambda x: ((x['pv_totalPower_kW']/x['NumberOfPanels'])*newNumberOfPanels)/4, axis=1)

# Giving a renewable fraction to each 15 minute row
df.loc[hasExcessPower, 'home_renewableFraction'] = 1
df.loc[~hasExcessPower, 'home_renewableFraction'] = (((df['pv_totalPower_kW'] * newNumberOfPanels / df['NumberOfPanels']) + ((df['load_power_kW'] - (df['pv_totalPower_kW'] * newNumberOfPanels / df['NumberOfPanels']))) 
                                                    * df['grid_renewableFraction_pct'])) / df['load_power_kW']

#df['stored_battery_energy'] = (6 if df['stored_battery_energy'].shift(-1) == 6 else 'TODO')

# Produces csv with final DataFrame
df.to_csv('customerData_modified.csv', index=False, encoding='utf-8')

# Prints total cost for one year
print('Total cost after export: ', (costOfPanels + df['cost_for_15m'].sum()))
print('Power consumed: ', ((df['load_power_kW'].sum())/4))
print('Power generated: ', (df['solar_energy_for_15m'].sum()))
print('Percentage Renewable: ', (df['home_renewableFraction'].mean()))
print('Total cost before solar: ', (df['priceBeforeSolar'].sum()))