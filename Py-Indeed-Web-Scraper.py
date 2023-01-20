"""
Indeed Web Scraper

Future Features (In order of priority)
	-Scrape multiple pages
		-Currently scrapes only the first page of results
			-Need to scrape multiple pages together, delete redundencies or duplicates
	-HTML element searching is hardcoded
		-Will likely break when sites update their client webpage
		-Workaround?
	-Add in a system to further vet canidates with description parameter
		-Grab all options first, then vet
	
Required Software
    -Python 
        -Version >= 3.6
        -Installation: https://www.python.org/downloads/
    -Python Modules
        -pyshorteners
            -Purpose: URL Shortening
            -Installation: https://pypi.org/project/pyshorteners/
		-selenium
			-Purpose: Web Scraping
			-Installation: https://pypi.org/project/selenium/
		-BeautifulSoup4
			-Purpose: HTML Parsing
			-Installation: https://pypi.org/project/beautifulsoup4/

Functionality
	-Scrapes job website data given a url with search results
		-Sends the result's details and links to the posting page
		-Can send the results via these formats
			-CSV Files (Saved locally)
			-TXT Files (Saved locally)
			-JSON Files (Saved locally)
			-SMS Messages 
	-Current supported sites
		-Indeed
		-LinkedIn
		-ZipRecruiter
		-CareerBuilder
"""


import csv
import logging
import warnings
import os
import time
import argparse
import pyshorteners
import itertools
import json
from Files.Modules.pySMS import pySMS
from bs4 import BeautifulSoup  
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from winreg import *

warnings.filterwarnings('ignore') 
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logging.getLogger("selenium").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

class Scraper():
	Data = None
	URL_Templates = None
	URL_Aliases = None
	ERROR_TEMPLATE = "A {0} exception occurred. Arguments:\n{1!r}"

	def __init__(self, args):
		self.Data = argparse.Namespace(**{ 
			"SITE": args.site,
			"TITLE": args.srch,
			"LOCATION": args.loc,
			"DATE": args.date,
			"DESCRIPTION" : args.desc,
			"CSV": args.csv,
			"TXT": args.txt,
			"JSON": args.json,
			"SMS": args.sms,
			"PHONE": args.ph,
			"EMAIL": args.e,
			"EMAIL_CREDS": args.ap
		})
		
		self.URL_Templates = {
			"Indeed" : {
				"Full" : "https://www.indeed.com/jobs?q={0}&l={1}&fromage={2}&",						 		 		#Description, Location, Days Ago Posted
				"Partial" : "https://www.indeed.com/"
			},
			"LinkedIn" : {
				"Full" : "https://www.linkedin.com/jobs/search/?keywords={0}&location={1}&f_TPR=r2592000",		 		#Description, Location, Days Ago Posted (30 Days or less)
				"Partial" : "https://www.linkedin.com/"
			},
			"ZipRecruiter" : {
				"Full" : "https://www.ziprecruiter.com/candidate/search?form=jobs-landing&search={0}&location={1}",     #Description, Location
				"Partial" : "https://www.ziprecruiter.com/"
			},
			"CareerBuilder" :{
				"Full" : "https://www.careerbuilder.com/jobs?keywords={0}&location={1}&posted={2}",						#Description, Location, Days Ago Posted
				"Partial" : "https://www.careerbuilder.com/"
			}
		}

	def Short_Url(self, url):										  			#URL shortener for better readibility and character limitations 
		shortener = pyshorteners.Shortener()
		return shortener.tinyurl.short(url)

	def Parse_Url(self, site=None):
		return (self.URL_Templates.get(self.Data.SITE if not site else site).get("Full").format(self.Data.TITLE.replace(" ", "+"), self.Data.LOCATION.replace(" ", "+"), self.Data.DATE))

	def Return_Default_Browser(self):								    #Only works on Windows
		try:
			with OpenKey(HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice") as key:
				options = Options()
				options.headless = True  											#Hide GUI
				Default = QueryValueEx(key, 'Progid')[0]
				if "Firefox" in Default:
					return {
						"Name" : "Firefox", 
						"Driver" : webdriver.Firefox(service_log_path=os.path.devnull, options=options)
					}				
				elif "Chrome" in Default:
					return {
						"Name" : "Chrome", 
						"Driver" : webdriver.Chrome(service_log_path=os.path.devnull, options=options)
					}				
				elif "Edge" in Default:
					return {
						"Name" : "Edge", 
						"Driver" : webdriver.Edge(service_log_path=os.path.devnull, options=options)
					}
				elif "Safari" in Default:
					return {
						"Name" : "Safari", 
						"Driver" : webdriver.Safari(service_log_path=os.path.devnull, options=options)
					}
				else:
					return {
						"Name" : Default,
						"Driver" : None
					}				
		except Exception as E:
			logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 

	def Scrap_Data(self, URL, Site):											#Scraping useful data
		try:
			Browser = self.Return_Default_Browser()
			if Browser["Driver"]:
				logging.info("Default browser found as '" + Browser["Name"] + "'")
				logging.info("Waiting for response from '" + URL + "' ...")
				Browser["Driver"].get(URL)	
				WebDriverWait(Browser["Driver"], 100).until(EC.url_contains(self.URL_Templates.get(Site).get("Partial")))	#Wait for page to load
				Html = Browser["Driver"].page_source
				Browser["Driver"].close()
				return Html
			else:
				raise Exception("Current default browser unsupported: " + Browser["Name"])
		except Exception as E:
			logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 
		return None
		
	def Parse_Indeed_Data(self, Data):								#Parses the data for a given website (Indeed)
		try:
			Job_Total = []
			if Data:
				Soup = BeautifulSoup(Data, features="html.parser")
				for All_Jobs in Soup.find_all(attrs={"class":"job_seen_beacon"}):
					Job_Attributes = {"Site" : "Indeed", "Link" : "", "Title" : "", "Company" : "", "Location" : "", "Date" : ""}
					for Title_Card in All_Jobs.find_all(name="h2", attrs={"class":"jobTitle"}): 		         				#Job Title/Link
						for Title in Title_Card.find_all(name="span"):
							Job_Attributes.update({"Title" : Title["title"]})
						for Link in Title_Card.find_all(name="a", attrs={"class":"jcs-JobTitle"}):
							Job_Attributes.update({"Link" : "indeed.com" + Link["href"]})
					for Company_Title_Card in All_Jobs.find_all("div", attrs={"class":"company_location"}): 					#Company Name
						for Company_Name in Company_Title_Card.find_all("a", attrs={"data-tn-element":"companyName"}):	
							Job_Attributes.update({"Company" : Company_Name.get_text()})
						for Location in Company_Title_Card.find_all("div", attrs={"class":"companyLocation"}):  				#Location
							Job_Attributes.update({"Location" : Location.get_text()})
					for Date_Title_Card in All_Jobs.find_all("table", attrs={"class":"jobCardShelfContainer"}):					#Date Posted
						for Date in Date_Title_Card.find_all("span", attrs={"class":"date"}):
							Job_Attributes.update({"Date" : Date.get_text().replace("PostedPosted", "Posted")})
					Job_Total.append(Job_Attributes)
			else:
				raise Exception("Missing HTML data")
			return Job_Total
		except Exception as E:
			logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 

	def Parse_LinkedIn_Data(self, Data):
		try:
			Job_Total = []
			if Data:
				Soup = BeautifulSoup(Data, features="html.parser")
				for All_Jobs in Soup.find_all(name="div", attrs={"class":"base-card"}):
					Job_Attributes = {"Site" : "LinkedIn", "Link" : "", "Title" : "", "Company" : "", "Location" : "", "Date" : ""}
					for Link in All_Jobs.find_all(name="a", attrs={"class":"base-card__full-link"}): 		         				#Link
						Job_Attributes.update({"Link" : Link["href"]})
					for Title_Card in All_Jobs.find_all(name="div", attrs={"class":"base-search-card__info"}): 							
						for Title in Title_Card.find_all("h3", attrs={"class":"base-search-card__title"}): 							#Title
							Job_Attributes.update({"Title" : Title.get_text()})
						for Company_Card in Title_Card.find_all("h4", attrs={"class":"base-search-card__subtitle"}):  				#Company Name
							for Company in Company_Card.find_all("a", attrs={"class":"hidden-nested-link"}):
								Job_Attributes.update({"Company" : Company.get_text()})
					for MetaData in All_Jobs.find_all(name="div", attrs={"class": "base-search-card__metadata"}):
						for Location in MetaData.find_all("span", attrs={"class": "job-search-card__location"}):					#Location
							Job_Attributes.update({"Location" : Location.get_text()})
						for Date in MetaData.find_all("time", attrs={"class":"job-search-card__listdate"}):							#Date Posted
							Job_Attributes.update({"Date" : str(Date["datetime"])})
					Job_Total.append(Job_Attributes)
			else:
				raise Exception("Missing HTML data")
			return Job_Total
		except Exception as E:
			logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 

	def Parse_ZipRecruiter_Data(self, Data):
		try:
			Job_Total = []
			if Data:
				Soup = BeautifulSoup(Data, features="html.parser")
				for All_Jobs in Soup.find_all(name="article", attrs={"class":"job_result"}): 		         				
					Job_Attributes = {"Site" : "ZipRecruiter", "Link" : "", "Title" : "", "Company" : "", "Location" : "", "Date" : ""}
					Job_Attributes.update({"Title" : All_Jobs["data-job-title"]})						#Title
					Job_Attributes.update({"Location" : All_Jobs["data-location"]})						#Location
					for Job_Card in All_Jobs.find_all(name="div", attrs={"class":"job_title_and_org"}):
						for Link in Job_Card.find_all(name="a", attrs={"class":"job_link"}):			#Link
							Job_Attributes.update({"Link" : Link["href"]})
						for Company in Job_Card.find_all(name="a", attrs={"class":"t_org_link"}):		#Company
							Job_Attributes.update({"Company" : Company.get_text()})
					Job_Total.append(Job_Attributes)
			else:
				raise Exception("Missing HTML data")
			return Job_Total
		except Exception as E:
			logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 
	
	def Parse_CareerBuilder_Data(self, Data):
		try:
			Job_Total = []
			if Data:
				Soup = BeautifulSoup(Data, features="html.parser")
				for All_Jobs in Soup.find_all(name="div", attrs={"class":"data-results"}):
					for Job_Card in All_Jobs.find_all(name="li", attrs={"class" : "data-results-content-parent"}):
						Job_Attributes = {"Site" : "CareerBuilder", "Link" : "", "Title" : "", "Company" : "", "Location" : "", "Date" : ""}
						for Date in Job_Card.find_all(name="div", attrs={"class":"data-results-publish-time"}):								#Date Posted
							Job_Attributes.update({"Date" : Date.get_text()})	
						for Title in Job_Card.find_all(name="div", attrs={"class":"data-results-title"}):									#Title
							Job_Attributes.update({"Title" : Title.get_text()})		
						for Job_Details in Job_Card.find_all(name="div", attrs={"class":"data-details"}):
							if Job_Details.get_text() != "":
								Details_List = list(filter(None, Job_Details.get_text().split("\n")))[:-1]
								if len(Details_List) > 1:		#Details list contains company and location
									Job_Attributes.update({"Company" : Details_List[0]})													#Company
									Job_Attributes.update({"Location" : Details_List[1]})													#Location
								elif len(Details_List) <= 1:	#Details list contains only the location
									Job_Attributes.update({"Company" : ""})											
									Job_Attributes.update({"Location" : Details_List[0]})													#Location
						for Link_Card in Job_Card.find_all(name="a", attrs={"class":"data-results-content"}):
							Job_Attributes.update({"Link" : self.URL_Templates["CareerBuilder"]["Partial"] + Link_Card["href"]})			#Link
						Job_Total.append(Job_Attributes)
			else:
				raise Exception("Missing HTML data")
			return Job_Total
		except Exception as E:
			logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 
			
	def Execute(self):									#Main method
		Start = time.time()												
		ParsedHtml = []
		if self.Data.SITE:								#Specific site was passed
			logging.info("Beginning scraping pass for " + "'" + str(self.Data.SITE) + "' ...")
			RawHtml = (self.Scrap_Data(self.Parse_Url(), self.Data.SITE))
			logging.info("Beginning html parsing ...")
			if RawHtml:
				if self.Data.SITE == "Indeed":
					ParsedHtml.append(self.Parse_Indeed_Data(RawHtml))
				elif self.Data.SITE == "LinkedIn":
					ParsedHtml.append(self.Parse_LinkedIn_Data(RawHtml))
				elif self.Data.SITE == "ZipRecruiter":
					ParsedHtml.append(self.Parse_ZipRecruiter_Data(RawHtml))
				elif self.Data.SITE == "CareerBuilder":
					ParsedHtml.append(self.Parse_CareerBuilder_Data(RawHtml))
			else:
				logging.error("No data was retrieved for '" + self.Data.SITE + "'")
		else:											#Scrap all sites
			for Iter, Site in enumerate(self.URL_Templates.keys(), 0):
				logging.info("Beginning scraping pass for " + "'" + Site + "' ...")
				RawHtml = self.Scrap_Data(self.Parse_Url(Site), Site)
				if RawHtml:
					logging.info("Beginning html parsing ...")
					if Site == "Indeed":
						ParsedHtml.append(self.Parse_Indeed_Data(RawHtml))
					elif Site == "LinkedIn":
						ParsedHtml.append(self.Parse_LinkedIn_Data(RawHtml))
					elif Site == "ZipRecruiter":
						ParsedHtml.append(self.Parse_ZipRecruiter_Data(RawHtml))
					elif Site == "CareerBuilder":
						ParsedHtml.append(self.Parse_CareerBuilder_Data(RawHtml))
				else:
					logging.error("No data was retrieved for '" + Site + "'")

		if ParsedHtml:
			FinalData = list(itertools.chain.from_iterable(ParsedHtml))
			if self.Data.CSV: 								#Writes data to a local .csv file
				try:
					Filename = "Job_List.csv"
					Path = os.path.dirname(os.path.realpath(__file__)).replace("\\", "/") + "/Files/"
					if not os.path.exists(Path):                  #If no files folder, create one
						logging.info("No 'Files' folder found in the root directory. Creating one ...")
						os.makedirs(Path)
					logging.info("Writing data to '" + (Filename) + "' ...")
					with open(Path + Filename, "w") as csvFile:
						write = csv.writer(csvFile, lineterminator="\n")
						for x in FinalData:
							write.writerow([x["Site"].strip(),
											x["Title"].strip(), 
											'=HYPERLINK("' + x["Link"].strip() + '","Application Link")',
											x["Company"].strip() if "Company" in x else "",
											x["Location"].strip() if "Location" in x else "", 
											x["Date"].strip() if "Date" in x else ""])
						csvFile.close()
					logging.info("File generated successfully at '" + Path + "' (" + str(len(FinalData)) + " canidate(s))")
				except IOError as IO: 
					logging.error(self.ERROR_TEMPLATE.format(type(IO).__name__, IO.args)) 
				except Exception as E:
					logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 
			if self.Data.TXT: 			#Writes data to a local .txt
				try:
					Filename = "Job_List.txt"
					Path = os.path.dirname(os.path.realpath(__file__)).replace("\\", "/") + "/Files/"
					if not os.path.exists(Path):                  #If no files folder, create one
						logging.info("No 'Files' folder found in the root directory. Creating one ...")
						os.makedirs(Path)
					logging.info("Writing data to '" + (Filename) + "' ...")
					with open(Path + Filename, "w") as txtFile:
						for x in FinalData:
							txtFile.write("Website: " + x["Site"].strip() + "\n" + 
										"Title: " + x["Title"].strip() + "\n" + 
										"Link: " + self.Short_Url(x["Link"]).strip() + "\n" + 
										"Company: " + x["Company"].strip() + "\n" + 
										"Location: " + x["Location"].strip() + "\n" + 
										"Date Published: " + x["Date"].strip() + "\n\n")
						txtFile.close()
					logging.info("File generated successfully at '" + Path + "' (" + str(len(FinalData)) + " canidate(s))")
				except IOError as IO: 
					logging.error(self.ERROR_TEMPLATE.format(type(IO).__name__, IO.args)) 
				except Exception as E:
					logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 
			if self.Data.JSON: 			#Writes data to a local .json
				try:
					Filename = "Job_List.json"
					Path = os.path.dirname(os.path.realpath(__file__)).replace("\\", "/") + "/Files/"
					if not os.path.exists(Path):                  #If no files folder, create one
						logging.info("No 'Files' folder found in the root directory. Creating one ...")
						os.makedirs(Path)
					logging.info("Writing data to '" + (Filename) + "' ...")
					with open(Path + Filename, "w") as jsonFile:
						Main = {}
						for count, x in enumerate(FinalData):
							Main.update( {
								"Canidate #" + str(count) : {	
									"Website" : x["Site"].strip(),
									"Title" : x["Title"].strip(), 
									"Link" : self.Short_Url(x["Link"]).strip(),
									"Company" : x["Company"].strip(),
									"Location" : x["Location"].strip(), 
									"Date Published" : x["Date"].strip()
								}	
							})   
						jsonFile.write(json.dumps(Main))
						jsonFile.close()
					logging.info("File generated successfully at '" + Path + "' (" + str(len(FinalData)) + " canidate(s))")
				except IOError as IO: 
					logging.error(self.ERROR_TEMPLATE.format(type(IO).__name__, IO.args)) 
				except Exception as E:
					logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 
			if self.Data.SMS: 			#Sends data to a number using a provided host email and phone number
				try:
					if not (self.Data.PHONE or self.Data.EMAIL or self.Data.EMAIL_CREDS): 
						raise Exception("Missing Parameters")
					else:	
						smsFinal = "Indeed Job Canidates:\n\n"
						logging.info("Formatting data to send to '" + self.Data.PHONE + "' ...")
						for x in FinalData:
							smsFinal += ("Website: " + x["Site"].strip() + "\n" +
										"Title: " + x["Title"] + "\n" +
										"Link: " + self.Short_Url(x["Link"]) + "\n" + 
										"Company: " + x["Company"] + "\n" + 
										"Location: " + x["Location"] + "\n" + 
										"Date Published: " + x["Date"] + "\n\n")
						SMS = pySMS(str(self.Data.PHONE), {"Username" : str(self.Data.EMAIL), "Password" : str(self.Data.EMAIL_CREDS)}, "Verizon")
						SMS.send("\n" + smsFinal)
				except IOError as IO: 
					logging.error(self.ERROR_TEMPLATE.format(type(IO).__name__, IO.args)) 
				except Exception as E:
					logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args))
		logging.info("Script run successfully (" + str(round(time.time() - Start, 2)) + " sec(s)" + ")")

if __name__ == "__main__": 	#Reads in arguments
	par = argparse.ArgumentParser(description="Indeed Web Scraper v0.75")

	#Required Parameters
	par.add_argument("-site", help="<Required> url argument for web scraper")
	par.add_argument("-srch", help="<Required> job title key words", required=True)

	#Optional parameters for narrowing search
	par.add_argument("-desc", nargs="+", help="posting description keywords")
	par.add_argument("-loc", help="job location")
	par.add_argument("-date", help="days since posted")

	#Parameters for type of export
	par.add_argument("-csv", help="<Optional> adds info to a local .csv file", action="store_true")
	par.add_argument("-txt", help="<Optional> adds info to a local .txt file", action="store_true")
	par.add_argument("-json", help="<Optional> adds info to a local .json file", action="store_true")
	par.add_argument("-sms", help="<Optional> sends data to specified number", action="store_true")

	#Parameters for phone message export
	par.add_argument("-ph", help="<Required for SMS> phone number")
	par.add_argument("-e", help="<Required for SMS> host email")
	par.add_argument("-ap", help="<Required for SMS> host email password/app password")

	Script = Scraper(par.parse_args())
	Script.Execute()