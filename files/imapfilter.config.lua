options.timeout = 1200
options.create = true
options.subscribe = true
options.expunge = true

gmail = IMAP {
    server = "imap.gmail.com",
    username = "dansullivan@gmail.com",
    password = os.getenv("GMAIL_APP_SPECIFIC_PASSWORD"),
    ssl = "tls1"
}

thinkspan = IMAP {
    server = "imap.gmail.com",
    username = "dan@thinkspan.com",
    password = os.getenv("THINKSPAN_GMAIL_APP_SPECIFIC_PASSWORD"),
    ssl = "tls1"
}

mailboxes, folders = gmail:list_all('*')
print("=== mailboxes")
for _, m in ipairs(mailboxes) do print(m) end
print("=== folders")
for _, f in ipairs(folders) do print(f) end

-- Thinkspan
messages = thinkspan["INBOX"]:select_all()
messages:move_messages(gmail["INBOX"])

-- Jira
messages = gmail["INBOX"]:contain_subject('[JIRA]'):contain_from('atlassian.net')
messages:move_messages(gmail["Keep/Jira"])
messages = gmail["INBOX"]:contain_from('no-reply@spartez-software.com')
messages:move_messages(gmail["Keep/Jira"])
messages = gmail["Keep/Jira"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Confluence
messages = gmail["INBOX"]:contain_subject('[Confluence]'):contain_from('atlassian.net')
messages:move_messages(gmail["Keep/Confluence"])
messages = gmail["Keep/Confluence"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- GitHub
messages = gmail["INBOX"]:contain_from("notifications@github.com")
messages:move_messages(gmail["Keep/GitHub"])
messages = gmail["Keep/GitHub"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Alumni
messages = gmail["INBOX"]:contain_from("masters-alumni@cs.uchicago.edu")
messages:move_messages(gmail['[Gmail]/Trash'])

-- Heroku
messages = gmail["INBOX"]:contain_from('bot@notifications.heroku.com')
messages:move_messages(gmail["Keep/Notifications/Heroku"])
messages = gmail["Keep/Notifications/Heroku"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Experian
messages = gmail["INBOX"]:contain_from('experian.com')
messages:move_messages(gmail["Keep/Notifications/Experian"])
messages = gmail["Keep/Notifications/Experian"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- American Express
messages = gmail["INBOX"]:contain_from('americanexpress.com')
messages:move_messages(gmail["Keep/Notifications/American Express"])


-- OnPay
messages = gmail["INBOX"]:contain_from('onpay.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Spectrum Emails
messages = gmail["INBOX"]:contain_from('spectrumemails.com')
messages:move_messages(gmail["Keep/Notifications/Spectrum"])

-- Intuit
messages = gmail["INBOX"]:contain_from('intuit@notifications.intuit.com')
messages:move_messages(gmail["Keep/Notifications/Intuit"])

-- Google
messages = gmail["INBOX"]:contain_from('payments-noreply@google.com')
messages:move_messages(gmail["Keep/Notifications/Google"])

-- TD Ameritrade
messages = gmail["INBOX"]:contain_from('client@notifications.tdameritrade.com')
messages:move_messages(gmail["Keep/Notifications/TD Ameritrade"])
messages = gmail["INBOX"]:contain_from('from@communications.tdameritrade.com')
messages:move_messages(gmail["Keep/Notifications/TD Ameritrade"])

-- Chattanooga Gas
messages = gmail["INBOX"]:contain_from('cgc@email.southerncompgas.com')
messages:move_messages(gmail["Keep/Notifications/Chattanooga Gas"])
messages = gmail["INBOX"]:contain_from('noreply@speedpay.com'):contain_subject('Chattanooga Gas')
messages:move_messages(gmail["Keep/Notifications/Chattanooga Gas"])

-- Eastside Utility
messages = gmail["INBOX"]:contain_from('CustomerService@PaymentServiceNetwork.com')
messages:move_messages(gmail["Keep/Notifications/Eastside Utility"])

-- Amazon
messages = gmail["INBOX"]:contain_from('no-reply-aws@amazon.com')
messages:move_messages(gmail["Keep/Notifications/AWS"])

-- Lowe's
messages = gmail["INBOX"]:contain_from('do-not-reply@notifications.lowes.com')
messages:move_messages(gmail["Keep/Notifications/Lowe's"])
messages = gmail["INBOX"]:contain_from('do-not-reply@confirmation.lowes.com')
messages:move_messages(gmail["Keep/Notifications/Lowe's"])
messages = gmail["INBOX"]:contain_from('do-not-reply@receipt.lowes.com')
messages:move_messages(gmail["Keep/Notifications/Lowe's"])

-- tZERO
messages = gmail["INBOX"]:contain_from('tzero.com')
messages:move_messages(gmail["Keep/Notifications/tZERO"])

-- Google Voice
messages = gmail["INBOX"]:contain_from('voice-noreply@google.com')
messages:move_messages(gmail["[Gmail]/Trash"])

-- Flynn's Barber Studio
messages = gmail["INBOX"]:contain_subject('Barber Studio')
messages:move_messages(gmail["[Gmail]/Trash"])

-- AMC Theatres
messages = gmail["INBOX"]:contain_from('amctheaters.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Sprint Estimation
messages = gmail["INBOX"]:contain_from('appfire.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Azure
messages = gmail["INBOX"]:contain_from('azure-noreply@microsoft.com')
messages:move_messages(gmail["Keep/Notifications/Azure"])

-- Chase
messages = gmail["INBOX"]:contain_from('no-reply@alertsp.chase.com')
messages:move_messages(gmail["Keep/Notifications/Chase"])

-- Cleanup Chipolte
messages = gmail["INBOX"]:contain_from('chipotle@email.chipotle.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- EPB
messages = gmail["INBOX"]:contain_from('customer.service@epb.net')
messages:move_messages(gmail["Keep/Notifications/EPB"])

-- Farmers Insurance
messages = gmail["INBOX"]:contain_from('noreply@policy.farmers.com')
messages:move_messages(gmail["Keep/Notifications/Farmers"])

-- Home Depot
messages = gmail["INBOX"]:contain_from('homedepot.com')
messages:move_messages(gmail["Keep/Notifications/Home Depot"])

-- Lawn Starter
messages = gmail["INBOX"]:contain_from('lawnstarter.com')
messages:move_messages(gmail["Keep/Notifications/Lawn Starter"])

-- Bitwarden 
messages = gmail["INBOX"]:contain_from('bitwarden.com')
messages:move_messages(gmail["Keep/Notifications/Bitwarden"])

-- LinkedIn
messages = gmail["INBOX"]:contain_from('messages-noreply@linkedin.com')
messages:move_messages(gmail["Keep/Notifications/LinkedIn"])

-- PayPal
messages = gmail["INBOX"]:contain_from('service@paypal.com')
messages:move_messages(gmail["Keep/Notifications/PayPal"])
messages = gmail["INBOX"]:contain_from('paypal@mail.paypal.com')
messages:move_messages(gmail["Keep/Notifications/PayPal"])

-- Schwab
messages = gmail["INBOX"]:contain_from('schwab.com')
messages:move_messages(gmail["Keep/Notifications/Schwab"])

-- Slack
messages = gmail["INBOX"]:contain_from('slack.com')
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('slackhq.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Starbucks
messages = gmail["INBOX"]:contain_from('starbucks.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Apple 
messages = gmail["INBOX"]:contain_from('no_reply@email.apple.com')
messages:move_messages(gmail["Keep/Notifications/Apple"])

-- Google Workspace
messages = gmail["INBOX"]:contain_from('workspace-noreply@google.com')
messages:move_messages(gmail["Keep/Notifications/Google"])

-- Twilio
messages = gmail["INBOX"]:contain_from('twilio.com')
messages:move_messages(gmail["Keep/Notifications/Twilio"])

-- Google Local Guides
messages = gmail["INBOX"]:contain_from('noreply-local-guides@google.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Venmo
messages = gmail["INBOX"]:contain_from('venmo.com')
messages:move_messages(gmail["Keep/Notifications/Venmo"])

-- Walmart
messages = gmail["INBOX"]:contain_from('walmart.com')
messages:move_messages(gmail["Keep/Notifications/Walmart"])

-- YouVersion
messages = gmail["INBOX"]:contain_from('youversion.com')
messages:move_messages(gmail['[Gmail]/Trash'])

--- Thinkspan
messages = gmail["INBOX"]:contain_from('postmaster@send.thinkspanstaging.com')
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('postmaster@send.thinkspan.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Sent
messages = gmail["[Gmail]/Sent Mail"]:is_older(1095)
messages:move_messages(gmail['[Gmail]/Trash'])
