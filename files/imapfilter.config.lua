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

-- Cleanup GitHub
messages = gmail["INBOX"]:contain_from("notifications@github.com")
messages:move_messages(gmail["Keep/GitHub"])
messages = gmail["Keep/GitHub"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Alumni
messages = gmail["INBOX"]:contain_from("masters-alumni@cs.uchicago.edu")
messages:move_messages(gmail["Keep/GitHub"])

-- Cleanup Heroku Notifications
messages = gmail["INBOX"]:contain_from('bot@notifications.heroku.com')
messages:move_messages(gmail["Keep/Notifications/Heroku"])
messages = gmail["Keep/Notifications/Heroku"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Experian Notifications
messages = gmail["INBOX"]:contain_from('experian.com')
messages:move_messages(gmail["Keep/Notifications/Experian"])
messages = gmail["Keep/Notifications/Experian"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup American Express Notifications
messages = gmail["INBOX"]:contain_from('americanexpress.com')
messages:move_messages(gmail["Keep/Notifications/American Express"])

-- Cleanup UofC Alumni
messages = gmail["INBOX"]:contain_to('masters-alumni@cs.uchicago.edu')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup OnPay
messages = gmail["INBOX"]:contain_from('doNotReply@app.onpay.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Spectrum Emails
messages = gmail["INBOX"]:contain_from('spectrumemails.com')
messages:move_messages(gmail["Keep/Notifications/Spectrum"])

-- Cleanup Intuit
messages = gmail["INBOX"]:contain_from('intuit@notifications.intuit.com')
messages:move_messages(gmail["Keep/Notifications/Intuit"])

-- Cleanup Google
messages = gmail["INBOX"]:contain_from('payments-noreply@google.com')
messages:move_messages(gmail["Keep/Notifications/Google"])

-- Cleanup TD Ameritrade
messages = gmail["INBOX"]:contain_from('client@notifications.tdameritrade.com')
messages:move_messages(gmail["Keep/Notifications/TD Ameritrade"])
messages = gmail["INBOX"]:contain_from('from@communications.tdameritrade.com')
messages:move_messages(gmail["Keep/Notifications/TD Ameritrade"])

-- Cleanup Chattanooga Gas
messages = gmail["INBOX"]:contain_from('cgc@email.southerncompgas.com')
messages:move_messages(gmail["Keep/Notifications/Chattanooga Gas"])
messages = gmail["INBOX"]:contain_from('noreply@speedpay.com'):contain_subject('Chattanooga Gas')
messages:move_messages(gmail["Keep/Notifications/Chattanooga Gas"])

-- Cleanup Eastside Utility
messages = gmail["INBOX"]:contain_from('CustomerService@PaymentServiceNetwork.com')
messages:move_messages(gmail["Keep/Notifications/Eastside Utility"])

-- Cleanup Amazon
messages = gmail["INBOX"]:contain_from('no-reply-aws@amazon.com')
messages:move_messages(gmail["Keep/Notifications/AWS"])

-- Cleanup Lowe's
messages = gmail["INBOX"]:contain_from('do-not-reply@notifications.lowes.com')
messages:move_messages(gmail["Keep/Notifications/Lowe's"])
messages = gmail["INBOX"]:contain_from('do-not-reply@confirmation.lowes.com')
messages:move_messages(gmail["Keep/Notifications/Lowe's"])
messages = gmail["INBOX"]:contain_from('do-not-reply@receipt.lowes.com')
messages:move_messages(gmail["Keep/Notifications/Lowe's"])

-- Cleanup tZERO
messages = gmail["INBOX"]:contain_from('no-reply@tzero.com')
messages:move_messages(gmail["Keep/Notifications/tZERO"])

-- Cleanup Google Voice
messages = gmail["INBOX"]:contain_from('voice-noreply@google.com')
messages:move_messages(gmail["[Gmail]/Trash"])

-- Cleanup Flynn's Barber Studio
messages = gmail["INBOX"]:contain_subject('Barber Studio')
messages:move_messages(gmail["[Gmail]/Trash"])

-- Cleanup AMC Theatres
messages = gmail["INBOX"]:contain_from('amctheaters.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Sprint Estimation
messages = gmail["INBOX"]:contain_from('appfire.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Azure
messages = gmail["INBOX"]:contain_from('azure-noreply@microsoft.com')
messages:move_messages(gmail["Keep/Notifications/Azure"])

-- Cleanup Chase
messages = gmail["INBOX"]:contain_from('no-reply@alertsp.chase.com')
messages:move_messages(gmail["Keep/Notifications/Chase"])

-- Cleanup Chipolte
messages = gmail["INBOX"]:contain_from('chipotle@email.chipotle.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup EPB
messages = gmail["INBOX"]:contain_from('customer.service@epb.net')
messages:move_messages(gmail["Keep/Notifications/EPB"])

-- Cleanup Farmers Insurance
messages = gmail["INBOX"]:contain_from('noreply@policy.farmers.com')
messages:move_messages(gmail["Keep/Notifications/Farmers"])

-- Cleanup Home Depot
messages = gmail["INBOX"]:contain_from('homedepot.com')
messages:move_messages(gmail["Keep/Notifications/Home Depot"])

-- Cleanup LinkedIn
messages = gmail["INBOX"]:contain_from('messages-noreply@linkedin.com')
messages:move_messages(gmail["Keep/Notifications/LinkedIn"])

-- Cleanup PayPal
messages = gmail["INBOX"]:contain_from('service@paypal.com')
messages:move_messages(gmail["Keep/Notifications/PayPal"])
messages = gmail["INBOX"]:contain_from('paypal@mail.paypal.com')
messages:move_messages(gmail["Keep/Notifications/PayPal"])

-- Cleanup Schwab
messages = gmail["INBOX"]:contain_from('schwab.com')
messages:move_messages(gmail["Keep/Notifications/Schwab"])

-- Cleanup Slack
messages = gmail["INBOX"]:contain_from('slack.com')
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('slackhq.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Starbucks
messages = gmail["INBOX"]:contain_from('starbucks.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Google Local Guides
messages = gmail["INBOX"]:contain_from('noreply-local-guides@google.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Venmo
messages = gmail["INBOX"]:contain_from('venmo.com')
messages:move_messages(gmail["Keep/Notifications/Venmo"])

-- Cleanup Walmart
messages = gmail["INBOX"]:contain_from('walmart.com')
messages:move_messages(gmail["Keep/Notifications/Walmart"])

-- Cleanup YouVersion
messages = gmail["INBOX"]:contain_from('youversion.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Sent
messages = gmail["[Gmail]/Sent Mail"]:is_older(1095)
messages:move_messages(gmail['[Gmail]/Trash'])

--- Cleanup Thinkspan
messages = gmail["INBOX"]:contain_from('postmaster@send.thinkspanstaging.com')
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('postmaster@send.thinkspan.com')
messages:move_messages(gmail['[Gmail]/Trash'])
