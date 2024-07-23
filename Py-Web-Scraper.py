"""
Web Scraper

Future Features (In order of priority)
	-Scrape multiple pages
		-Currently scrapes only the first page of results
			-Need to scrape multiple pages together, delete redundencies or duplicates
	-HTML element searching is hardcoded
		-Will likely break when sites update their client webpage
		-Workaround?
	-Add a means of texting or emailing potential canidates
		-Texting is difficult since IOS and probably other manufactures tend to block short links
		-Can potentially generate a dummy email to send canidates that way
			-Will need a recipient email address (Use a parameter)

Bugs
	-Date posted in missing from Indeed (Needs update to HTML parser, check the metadata)
	-Sometimes when choosing a different output format, number of canidates changes
	-ZipRecruiter is broken (Needs update to HTML parser)
	-CareerBuilder is broken (Needs update to HTML parser)
	
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
			-Note: Only works with selenium 4.9.1
		-BeautifulSoup4
			-Purpose: HTML Parsing
			-Installation: https://pypi.org/project/beautifulsoup4/

Functionality
	-Scrapes job website data given a url with search results
		-Sends the result's details and links to the posting page
		-Can send the results via these formats
			-CSV Files 
			-TXT Files 
			-JSON Files 
	-Current supported sites
		-Indeed
		-LinkedIn
		-ZipRecruiter (Currently Broken)
		-CareerBuilder (Currently Broken)
"""

import sys
import csv
import logging
import warnings
import os
import time
import argparse
import pyshorteners
import itertools
import json
import webbrowser
from bs4 import BeautifulSoup  
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ERRORTEMPLATE = "A {0} exception occurred. Arguments:\n{1!r}"
warnings.filterwarnings('ignore') 
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logging.getLogger("selenium").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

class Scraper():
	Data = None
	URLTemplates = None
	URLAliases = None

	def __init__(self, args):
		self.Data = argparse.Namespace(**{ 
			"SITE": args.site,
			"TITLE": args.srch,
			"LOCATION": args.loc,
			"DATE": args.date,
			"DESCRIPTION" : args.desc,
			"CSV": args.csv,
			"TXT": args.txt,
			"JSON": args.json
		})
		
		self.URLTemplates = {
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

	def ShortUrl(self, url):										  													#URL shortener for better readibility and character limitations 
		shortener = pyshorteners.Shortener()
		return shortener.tinyurl.short(url)

	def ParseUrl(self, site=None):
		SiteName = self.URLTemplates.get(self.Data.SITE if not site else site)
		SiteNameFull = SiteName.get("Full")
		return SiteNameFull.format(self.Data.TITLE.replace(" ", "+"), self.Data.LOCATION.replace(" ", "+"), self.Data.DATE)

	def ReturnDefaultBrowser(self):								    													
		try:
			DefaultBrowser = webbrowser.get()
			DefaultBrowserName = DefaultBrowser.name
			BrowserOptions = Options()
			BrowserOptions.headless = True  	
			if "firefox" in DefaultBrowserName:
				return {
					"Name" : "Firefox", 
					"Driver" : webdriver.Firefox(service_log_path=os.path.devnull, options=BrowserOptions)
				}				
			elif "chrome" in DefaultBrowserName:
				return {
					"Name" : "Chrome", 
					"Driver" : webdriver.Chrome(service_log_path=os.path.devnull, options=BrowserOptions)
				}				
			elif "edge" in DefaultBrowserName:
				return {
					"Name" : "Edge", 
					"Driver" : webdriver.Edge(service_log_path=os.path.devnull, options=BrowserOptions)
				}
			elif "safari" in DefaultBrowserName:
				return {
					"Name" : "Safari", 
					"Driver" : webdriver.Safari(service_log_path=os.path.devnull, options=BrowserOptions)
				}
			else:
				return {
					"Name" : DefaultBrowserName,
					"Driver" : None
				}			
		except Exception as E:
			logging.error(ERRORTEMPLATE.format(type(E).__name__, E.args)) 
		return None

	def ScrapData(self, URL, Site):											
		try:
			Browser = self.ReturnDefaultBrowser()
			if Browser is None: 
				raise Exception("Error in getting the default browser")
			if Browser is not None and Browser["Driver"]:
				logging.info("Default browser found as '" + Browser["Name"] + "'")
				logging.info("Waiting for response from '" + URL + "' ...")
				Browser["Driver"].get(URL)	
				WebDriverWait(Browser["Driver"], 100).until(EC.url_contains(self.URLTemplates.get(Site).get("Partial")))	#Wait for page to load
				Html = Browser["Driver"].page_source
				Browser["Driver"].close()
				return Html
			else:
				raise Exception("Current default browser unsupported: " + Browser["Name"])
		except Exception as E:
			logging.error(ERRORTEMPLATE.format(type(E).__name__, E.args)) 
		return None
		
	def ParseIndeedData(self, Data):								
		try:
			JobTotal = []
			if Data:
				Soup = BeautifulSoup(Data, features="html.parser")
				for AllJobs in Soup.find_all(attrs={"class":"job_seen_beacon"}):
					JobAttributes = {"Site" : "Indeed", "Link" : "", "Title" : "", "Company" : "", "Location" : "", "Date" : ""}
					for TitleCard in AllJobs.find_all(name="h2", attrs={"class":"jobTitle"}): 		         				#Job Title/Link
						for Title in TitleCard.find_all(name="span"):
							JobAttributes.update({"Title" : Title["title"]})
						for Link in TitleCard.find_all(name="a", attrs={"class":"jcs-JobTitle"}):
							JobAttributes.update({"Link" : "indeed.com" + Link["href"]})
					for CompanyTitleCard in AllJobs.find_all("div", attrs={"class":"company_location"}): 					#Company Name
						for CompanyName in CompanyTitleCard.find_all("span", attrs={"data-testid":"company-name"}):	
							JobAttributes.update({"Company" : CompanyName.get_text()})
						for Location in CompanyTitleCard.find_all("div", attrs={"data-testid":"text-location"}):  			#Location
							JobAttributes.update({"Location" : Location.get_text()})
					for DateTitleCard in AllJobs.find_all("table", attrs={"class":"jobCardShelfContainer"}):				#Date Posted
						for Date in DateTitleCard.find_all("span", attrs={"class":"date"}):
							JobAttributes.update({"Date" : Date.get_text().replace("PostedPosted", "Posted")})
					JobTotal.append(JobAttributes)
			else:
				raise Exception("Missing HTML data")
			return JobTotal
		except Exception as E:
			logging.error(ERRORTEMPLATE.format(type(E).__name__, E.args)) 

	def ParseLinkedInData(self, Data):
		try:
			JobTotal = []
			if Data:
				Soup = BeautifulSoup(Data, features="html.parser")
				for AllJobs in Soup.find_all(name="div", attrs={"class":"base-card"}):
					JobAttributes = {"Site" : "LinkedIn", "Link" : "", "Title" : "", "Company" : "", "Location" : "", "Date" : ""}
					for Link in AllJobs.find_all(name="a", attrs={"class":"base-card__full-link"}): 		         		#Link
						JobAttributes.update({"Link" : Link["href"]})
					for TitleCard in AllJobs.find_all(name="div", attrs={"class":"base-search-card__info"}): 							
						for Title in TitleCard.find_all("h3", attrs={"class":"base-search-card__title"}): 					#Title
							JobAttributes.update({"Title" : Title.get_text()})
						for CompanyCard in TitleCard.find_all("h4", attrs={"class":"base-search-card__subtitle"}):  		#Company Name
							for Company in CompanyCard.find_all("a", attrs={"class":"hidden-nested-link"}):
								JobAttributes.update({"Company" : Company.get_text()})
					for MetaData in AllJobs.find_all(name="div", attrs={"class": "base-search-card__metadata"}):
						for Location in MetaData.find_all("span", attrs={"class": "job-search-card__location"}):			#Location
							JobAttributes.update({"Location" : Location.get_text()})
						for Date in MetaData.find_all("time", attrs={"class":"job-search-card__listdate"}):					#Date Posted
							JobAttributes.update({"Date" : str(Date["datetime"])})
					JobTotal.append(JobAttributes)
			else:
				raise Exception("Missing HTML data")
			return JobTotal
		except Exception as E:
			logging.error(ERRORTEMPLATE.format(type(E).__name__, E.args)) 

	def ParseZipRecruiterData(self, Data):
		try:
			JobTotal = []
			if Data:
				Soup = BeautifulSoup(Data, features="html.parser")
				for AllJobs in Soup.find_all(name="article", attrs={"class":"job_result"}): 		         				
					JobAttributes = {"Site" : "ZipRecruiter", "Link" : "", "Title" : "", "Company" : "", "Location" : "", "Date" : ""}
					JobAttributes.update({"Title" : AllJobs["data-job-title"]})												#Title
					JobAttributes.update({"Location" : AllJobs["data-location"]})											#Location
					for JobCard in AllJobs.find_all(name="div", attrs={"class":"job_title_and_org"}):
						for Link in JobCard.find_all(name="a", attrs={"class":"job_link"}):									#Link
							JobAttributes.update({"Link" : Link["href"]})
						for Company in JobCard.find_all(name="a", attrs={"class":"t_org_link"}):							#Company
							JobAttributes.update({"Company" : Company.get_text()})
					JobTotal.append(JobAttributes)
			else:
				raise Exception("Missing HTML data")
			return JobTotal
		except Exception as E:
			logging.error(ERRORTEMPLATE.format(type(E).__name__, E.args)) 
	
	def ParseCareerBuilderData(self, Data):
		try:
			JobTotal = []
			if Data:
				Soup = BeautifulSoup(Data, features="html.parser")
				for AllJobs in Soup.find_all(name="div", attrs={"class":"data-results"}):
					for JobCard in AllJobs.find_all(name="li", attrs={"class" : "data-results-content-parent"}):
						JobAttributes = {"Site" : "CareerBuilder", "Link" : "", "Title" : "", "Company" : "", "Location" : "", "Date" : ""}
						for Date in JobCard.find_all(name="div", attrs={"class":"data-results-publish-time"}):				#Date Posted
							JobAttributes.update({"Date" : Date.get_text()})	
						for Title in JobCard.find_all(name="div", attrs={"class":"data-results-title"}):					#Title
							JobAttributes.update({"Title" : Title.get_text()})		
						for JobDetails in JobCard.find_all(name="div", attrs={"class":"data-details"}):
							if JobDetails.get_text() != "":
								DetailsList = list(filter(None, JobDetails.get_text().split("\n")))[:-1]
								if len(DetailsList) > 1:		#Details list contains company and location
									JobAttributes.update({"Company" : DetailsList[0]})										#Company
									JobAttributes.update({"Location" : DetailsList[1]})										#Location
								elif len(DetailsList) <= 1:	#Details list contains only the location
									JobAttributes.update({"Company" : ""})											
									JobAttributes.update({"Location" : DetailsList[0]})										#Location
						for LinkCard in JobCard.find_all(name="a", attrs={"class":"data-results-content"}):
							JobAttributes.update({"Link" : self.URLTemplates["CareerBuilder"]["Partial"] + LinkCard["href"]})			
						JobTotal.append(JobAttributes)
			else:
				raise Exception("Missing HTML data")
			return JobTotal
		except Exception as E:
			logging.error(ERRORTEMPLATE.format(type(E).__name__, E.args)) 
			
	def Execute(self):									
		Start = time.time()												
		ParsedHtml = []
		if self.Data.SITE:								
			logging.info("Beginning scraping pass for " + "'" + str(self.Data.SITE) + "' ...")
			RawHtml = (self.ScrapData(self.ParseUrl(), self.Data.SITE))
			logging.info("Beginning html parsing ...")
			if RawHtml:
				if self.Data.SITE == "Indeed":
					ParsedHtml.append(self.ParseIndeedData(RawHtml))
				elif self.Data.SITE == "LinkedIn":
					ParsedHtml.append(self.ParseLinkedInData(RawHtml))
				elif self.Data.SITE == "ZipRecruiter":
					ParsedHtml.append(self.ParseZipRecruiterData(RawHtml))
				elif self.Data.SITE == "CareerBuilder":
					ParsedHtml.append(self.ParseCareerBuilderData(RawHtml))
			else:
				logging.error("No data was retrieved for '" + self.Data.SITE + "'")
		else:											
			for Iter, Site in enumerate(self.URLTemplates.keys(), 0):
				logging.info("Beginning scraping pass for " + "'" + Site + "' ...")
				RawHtml = self.ScrapData(self.Parse_Url(Site), Site)
				if RawHtml:
					logging.info("Beginning html parsing ...")
					if Site == "Indeed":
						ParsedHtml.append(self.ParseIndeedData(RawHtml))
					elif Site == "LinkedIn":
						ParsedHtml.append(self.ParseLinkedInData(RawHtml))
					elif Site == "ZipRecruiter":
						ParsedHtml.append(self.ParseZipRecruiterData(RawHtml))
					elif Site == "CareerBuilder":
						ParsedHtml.append(self.ParseCareerBuilderData(RawHtml))
				else:
					logging.error("No data was retrieved for '" + Site + "'")

		if ParsedHtml:
			FinalData = list(itertools.chain.from_iterable(ParsedHtml))
			if self.Data.CSV: 										
				try:
					Filename = "JobList.csv"
					Path = os.path.dirname(os.path.realpath(__file__)).replace("\\", "/") + "/Files/"
					if not os.path.exists(Path):                  	
						logging.info("No 'Files' folder found in the root directory. Creating one ...")
						os.makedirs(Path)
					logging.info("Writing data to '" + (Filename) + "' ...")
					with open(Path + Filename, "w") as csvFile:
						write = csv.writer(csvFile, lineterminator="\n")
						for DataRow in FinalData:
							write.writerow([DataRow["Site"].strip(),
											DataRow["Title"].strip(), 
											'=HYPERLINK("' + DataRow["Link"].strip() + '","Application Link")',
											DataRow["Company"].strip() if "Company" in DataRow else "",
											DataRow["Location"].strip() if "Location" in DataRow else "", 
											DataRow["Date"].strip() if "Date" in DataRow else ""])
						csvFile.close()
					logging.info("File generated successfully at '" + Path + "' (" + str(len(FinalData)) + " canidate(s))")
				except IOError as IO: 
					logging.error(ERRORTEMPLATE.format(type(IO).__name__, IO.args)) 
				except Exception as E:
					logging.error(ERRORTEMPLATE.format(type(E).__name__, E.args)) 
			if self.Data.TXT: 										
				try:
					Filename = "JobList.txt"
					Path = os.path.dirname(os.path.realpath(__file__)).replace("\\", "/") + "/Files/"
					if not os.path.exists(Path):                  	
						logging.info("No 'Files' folder found in the root directory. Creating one ...")
						os.makedirs(Path)
					logging.info("Writing data to '" + (Filename) + "' ...")
					with open(Path + Filename, "w") as txtFile:
						for x in FinalData:
							txtFile.write("Website: " + x["Site"].strip() + "\n" + 
										"Title: " + x["Title"].strip() + "\n" + 
										"Link: " + self.ShortUrl(x["Link"]).strip() + "\n" + 
										"Company: " + x["Company"].strip() + "\n" + 
										"Location: " + x["Location"].strip() + "\n" + 
										"Date Published: " + x["Date"].strip() + "\n\n")
						txtFile.close()
					logging.info("File generated successfully at '" + Path + "' (" + str(len(FinalData)) + " canidate(s))")
				except IOError as IO: 
					logging.error(ERRORTEMPLATE.format(type(IO).__name__, IO.args)) 
				except Exception as E:
					logging.error(ERRORTEMPLATE.format(type(E).__name__, E.args)) 
			if self.Data.JSON: 			
				try:
					Filename = "JobList.json"
					Path = os.path.dirname(os.path.realpath(__file__)).replace("\\", "/") + "/Files/"
					if not os.path.exists(Path):                  
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
									"Link" : self.ShortUrl(x["Link"]).strip(),
									"Company" : x["Company"].strip(),
									"Location" : x["Location"].strip(), 
									"Date Published" : x["Date"].strip()
								}	
							})   
						jsonFile.write(json.dumps(Main))
						jsonFile.close()
					logging.info("File generated successfully at '" + Path + "' (" + str(len(FinalData)) + " canidate(s))")
				except IOError as IO: 
					logging.error(ERRORTEMPLATE.format(type(IO).__name__, IO.args)) 
				except Exception as E:
					logging.error(ERRORTEMPLATE.format(type(E).__name__, E.args)) 
		logging.info("Script run successfully (" + str(round(time.time() - Start, 2)) + " sec(s)" + ")")

if __name__ == "__main__": 	
	par = argparse.ArgumentParser(description="Indeed Web Scraper v0.75")

	#Required Parameters
	par.add_argument("-site", help="<Required> Site to search for", required=True)
	par.add_argument("-srch", help="<Required> Job title key words", required=True)

	#Optional parameters for narrowing search
	par.add_argument("-desc", nargs="+", help="Posting description keywords")
	par.add_argument("-loc", help="Job location")
	par.add_argument("-date", help="Days since posted")

	#Parameters for type of export
	par.add_argument("-csv", help="<Optional> Adds info to a local .csv file", action="store_true")
	par.add_argument("-txt", help="<Optional> Adds info to a local .txt file", action="store_true")
	par.add_argument("-json", help="<Optional> Adds info to a local .json file", action="store_true")

	Script = Scraper(par.parse_args())
	Script.Execute()