import smtplib
import logging

class pySMS():
	ERROR_TEMPLATE = "A {0} exception occurred. Arguments:\n{1!r}"
	Phone_Number = ""
	Host_Email = {
		"Username" : "",
		"Password" : ""
	}
	SMS_Gateway_Domains = {
		"at@t" : "@mms.att.net",
		"tmobile" : "@tmomail.net",
		"verizon" : "@vtext.net",
		"sprint" : "@page.nextel.com",
		"alltel" : "@sms.alltelwireless.com",
		"boost mobile" : "@sms.myboostmobile.com",
		"cricket wireless": "@mms.cricketwireless.net",
		"metroPCS" : "@mymetropcs.com",
		"republic wireless" : "@text.republicwireless.com",
		"us cellular" : "@email.uscc.net",
		"virgin mobile" : "@vmobl.com"
	}

	def __init__(self, Num, Host, Carrier):
		try:
			self.Phone_Number = Num + "{}".format(self.SMS_Gateway_Domains[Carrier.lower()])
			self.Host_Email = Host
		except Exception as E:
			logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 
	
	def send(self, Data):
		try:
			with smtplib.SMTP("smtp.gmail.com", 587) as Connection:
				Connection.starttls()
				Connection.login(self.Host_Email["Username"], self.Host_Email["Password"])
				Connection.sendmail(self.Host_Email["Username"], self.Phone_Number, Data[:Data.rfind("\n")].encode('utf-8'))
				Connection.close()
		except smtplib.SMTPException as STMP:
			logging.error(self.ERROR_TEMPLATE.format(type(STMP).__name__, STMP.args)) 
		except Exception as E:
			logging.error(self.ERROR_TEMPLATE.format(type(E).__name__, E.args)) 
