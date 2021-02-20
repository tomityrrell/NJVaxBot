import os
import time

from datetime import datetime
import pytz

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

import chivaxbot as chivaxbot
#import chivaxbot

retries = 5

# Get current date and create directory for new files
now = datetime.now(pytz.timezone('America/New_York'))
print("Today is {}".format(now.date()))

try:
    os.mkdir("./images/{}".format(now.date().__str__()))
except FileExistsError:
    pass

# County populations from wikipedia, sorted alphabetically by county:  https://en.wikipedia.org/wiki/List_of_counties_in_New_Jersey
county_pops = np.array([263670, 932202, 445349, 506471, 92039, 149527, 798975, 291636, 672391, 124371, 367430, 825062, 618795, 491845, 607186, 501826, 62385, 328934, 140488, 556341, 105267])
state_pop = county_pops.sum()

# # Pull covid case/death data from https://github.com/nytimes/covid-19-data
# all_url = "https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv"
# today_url = "https://raw.githubusercontent.com/nytimes/covid-19-data/master/live/us-counties.csv"
# res = requests.get(today_url)
# covid = pd.DataFrame(res.text)


def get_driver(mode="Firefox"):
    options = Options()
    options.headless = True
    if mode == "Firefox":
        driver = webdriver.Firefox(options=options, executable_path='./geckodriver')
    elif mode == "Remote":
        driver = webdriver.Remote(command_executor="http://localhost:4444/wd/hub", options=options)
    driver.implicitly_wait(5)

    return driver


def scraper(mode="Firefox"):
    driver = get_driver(mode)

    # TODO Create single scrapping method for case and vaccine data

    # DATA SOURCE #1
    #
    # Pull case data from NJ Covid Dashboard at https://njhealth.maps.arcgis.com/apps/opsdashboard/index.html#/795729487af44255a1357c73fd8d8b4e
    #

    # URL
    case_data_url = "https://njhealth.maps.arcgis.com/apps/opsdashboard/index.html#/795729487af44255a1357c73fd8d8b4e"
    driver.get(case_data_url)

    # XPATH
    # Scrape case data by county
    case_data_xpath = "//span[contains(@id,'ember') and contains(@class,'flex') and @style='']"
    case_data_elements = driver.find_elements(By.XPATH, case_data_xpath)
    while not case_data_elements and retries > 0:
        print("Case data elements not found.  {} attempt(s) left.  Retrying in 5 seconds...".format(retries))
        time.sleep(5)
        retries = retries - 1
        case_data_elements = driver.find_elements(By.XPATH, case_data_xpath)

    # DATA PROCESSING
    county_names = list(map(lambda e: e.find_elements_by_tag_name("p")[0].text.replace(" County", "").replace(" ", "_").lower(), case_data_elements))
    cases_field_names = list(filter(lambda s: s != "", map(lambda t: t.text[t.text.index(" "):].strip().replace("Total ", ""), case_data_elements[0].find_elements_by_tag_name("td"))))
    cases_data = list(map(lambda t: list(filter(lambda s: s != "", map(lambda t: t.text.replace(",", "").strip().split(" ")[0], t.find_elements_by_tag_name("td")))), case_data_elements))
    cases_df = pd.DataFrame(cases_data, index=county_names, columns=cases_field_names)

    # DATA SOURCE # 2
    #
    # Pull vaccine data from NJ Covid Dashboard at https://njhealth.maps.arcgis.com/apps/opsdashboard/index.html#/c99909df3f994c2ab07134f9f746000c
    #

    # URL
    vaccine_data_url = "https://njhealth.maps.arcgis.com/apps/opsdashboard/index.html#/c99909df3f994c2ab07134f9f746000c"
    driver.get(vaccine_data_url)

    # vaccine_data_url = "https://njhealth.maps.arcgis.com/apps/MapSeries/index.html?appid=50c2c6af93364b4da9c0bf6327c04b45&folderid=e5d6362c0f1f4f9684dc650f00741b24"
    # driver.get(vaccine_data_url)
    #
    # vaccination_tab_xpath = "//button[contains(text(),'Vaccination Overview')]"
    # driver.find_element_by_xpath(vaccination_tab_xpath).click()

    # XPATH
    # Scrape vaccine data by county
    vaccine_data_xpath = "//span[contains(@id,'ember') and contains(@class,'flex')]"
    vaccine_data_elements = driver.find_elements(By.XPATH, vaccine_data_xpath)
    while not vaccine_data_elements and retries > 0:
        print("Vaccine data elements not found.  {} attempt(s) left.  Retrying in 5 seconds...".format(retries))
        retries = retries - 1
        time.sleep(5)
        case_data_elements = driver.find_elements(By.XPATH, case_data_xpath)

    # DATA PROCESSING
    vaccine_data = list(map(lambda s: s.text.replace(",","").replace(" COUNTY", "").replace(" Doses Administered", "").replace(" ", "_").lower().split("\n"), vaccine_data_elements))
    vaccine_df = pd.DataFrame(vaccine_data, columns=["county", "Vaccine Doses"])
    vaccine_df.index = vaccine_df.county
    vaccine_df.drop("county", axis=1, inplace=True)

    driver.quit()

    # COMBINE DATA SOURCES
    # Merge cases and vaccine data into one DF
    covid_df = cases_df.merge(vaccine_df, left_index=True, right_index=True).astype("int")
    covid_df.sort_index(inplace=True)
    covid_df.sort_index(axis=1, inplace=True)
    covid_df["Population"] = county_pops

    covid_df.to_csv("./data/nj_covid_{}.csv".format(now.date()), index_label="County")

    # DATA NORMALIZATION
    # Normalize df and create discrepancy columns
    scaler = StandardScaler().fit(covid_df)
    ndf = pd.DataFrame(scaler.transform(covid_df))
    ndf.index = covid_df.index
    ndf.columns = covid_df.columns
    ndf["Vaccine-Case Discrepancy"] = ndf["Vaccine Doses"] - ndf["Confirmed Cases"]
    ndf["Vaccine-Death Discrepancy"] = ndf["Vaccine Doses"] - ndf["Confirmed Deaths"]

    print("Scrapping successful!")

    return covid_df, ndf


def imager(data_dict, palette, name):
    colors = chivaxbot.get_colors_dict(data_dict, palette, name)
    chivaxbot.write_svg("./images/New_Jersey_Counties_Outline.svg", ["./images/{}/{}_{}.png".format(now.date(), name, now.date())], colors)

    print("{} imaging successful!".format(name))


if __name__ == '__main__':
    df, ndf = scraper(mode="Firefox")

    # Percentages inter-county
    df_by_county = df.divide(df.Population, axis=0)

    # Percentages intra-county/state level
    df_by_category = df/df.sum()

    imager(df["Vaccine Doses"].to_dict(), chivaxbot.vax_colorscale, "vaccines")
    imager(df["Confirmed Cases"].to_dict(), chivaxbot.deaths_colorscale, "cases"),
    imager(df["Confirmed Deaths"].to_dict(), chivaxbot.vax_colorscale, "deaths")

    disc_colorscale = ["#641e16", " #922b21", " #c0392b", " #e6b0aa ", " #f9ebea"]
    imager(ndf["Vaccine-Case Discrepancy"].to_dict(), disc_colorscale, "case-vax-disc")
    imager(ndf["Vaccine-Death Discrepancy"].to_dict(), disc_colorscale, "death-vax-disc")

    imager(df_by_county["Confirmed Deaths"].to_dict(), disc_colorscale, "deaths_by_county")