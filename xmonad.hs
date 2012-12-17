--Xmonad Configuration File---
--Dan Sullivan, started June, 8, 2010

import XMonad
import XMonad.Hooks.DynamicLog

-- The main function.
main = xmonad =<< statusBar myBar myPP toggleStrutsKey myConfig

-- Command to launch the bar.  Either of these appears to work.
myBar = "xmobar"
--myBar = "dzen2 -l 1"

-- Custom PP, configure it as you like. It determines what is being written to the bar.
myPP = xmobarPP { ppCurrent = xmobarColor "#429942" "" . wrap "<" ">" }

--Key binding to toggle the gap for the bar.
--this is mod+ b
--http://hackage.haskell.org/packages/archive/X11/1.6.0/doc/html/Graphics-X11-Types.html
toggleStrutsKey XConfig {XMonad.modMask = modMask} = (modMask, xK_b)

myConfig = defaultConfig {
    --this sets the default key binding to the windows key.
    --modMask = mod4Mask
    terminal="xterm"
    --terminal="rxvt"
}
