
Config {
       --font = "-misc-fixed-*-*-*-*-10-*-*-*-*-*-*-*"
       --This appears to work with any from xfontsel 12/28/2012
       font = "-nil-profont-medium-r-normal--12-120-72-72-c-60-iso8859-1"
       --font = "-*-profont-*-*-*-*-12-*-*-*-*-*-*-*"
       --Place the bar at the bottom, centered with 75% of the screen width
       --, position = BottomW C 75
       , position = Top
       , bgColor = "black"
       , fgColor = "grey"
       --Show on all desktops (default = True)
       , allDesktops = True
       , border = BottomB
       , borderColor = "#af00ff"
       --Send the window to the bottom of the window stack initially
       , lowerOnStart = True
       , commands = [
            Run Network "eno1" ["-L","0","-H","32","--normal","grey","--high","grey"] 10
            , Run Cpu ["-L","3","-H","50","--normal","grey","--high","grey"] 10
            , Run Memory ["-t","Mem: <usedratio>%"] 10
            , Run StdinReader
            , Run Com "echo" ["dps2"] "echoInitials" 0 --0 means run only once
            , Run Com "date" [] "customClock" 10 --do it once per second (last parameter is tenths of second).
            , Run Com "echo" ["-e", "\"\\xb7\""] "fancyDot" 0
            , Run Com "dropbox-cli" ["status"] "dropboxStatus" 10
       ]
       --The character to be used for indicating commands in the output template.
       , sepChar = "%"
       --The text before the first character will be left aligned, the text between them
       --will be centered, and the text to the right of the last character will be right aligned.
       , alignSep = "}{"
       , template = "%echoInitials% <fc=#8ae234>.</fc> %eno1% %memory% %cpu% %dropboxStatus% %customClock% }{ %StdinReader%"
}
