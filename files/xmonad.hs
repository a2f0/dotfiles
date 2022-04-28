--Xmonad Configuration File
--https://wiki.haskell.org/Xmonad/Config_archive/yiannist's_xmonad.hs

import XMonad
import XMonad.Hooks.DynamicLog
import XMonad.Hooks.ManageDocks
import XMonad.Hooks.EwmhDesktops
import XMonad.Config.Xfce
import XMonad.Util.EZConfig
--import Xmonad.Util.Paste

import qualified Data.Map as M

-- The main function.
-- main = xmonad =<< statusBar myBar myPP toggleStrutsKey myConfig
--main = xmonad =<< statusBar myBar toggleStrutsKey myConfig

-- Command to launch the bar.  Either of these appears to work.
myBar = "xmobar"
--myBar = "dzen2 -l 1"

-- Custom PP, configure it as you like. It determines what is being written to the bar.
--myPP = xmobarPP {
--     ppCurrent = xmobarColor "#429942" "" . wrap "<" ">"
--}
main :: IO ()
main = xmonad $ ewmh xfceConfig
  { terminal = "xterm"
  --make mod the windows key
  --, modMask = mod4Mask
  , borderWidth = 1
  , focusFollowsMouse = True
  , focusedBorderColor = "#0033ff"
  , manageHook = manageHook xfceConfig <+> myManageHook
  } `additionalKeys` myKeys
  where
    myKeys = [
                 ((mod4Mask,               xK_f           ), spawn "thunar")
               , ((mod4Mask,               xK_a           ), spawn "xdotool getwindowfocus windowfocus --sync type --delay 100 `cat ~/.bsdad`")
               , ((mod4Mask,               xK_s           ), spawn "xdotool getactivewindow windowfocus --sync type --delay 100 `cat ~/.bsdad`")
               --, ((mod4Mask,               xK_s           ), pasteString "foo bar")
               , ((mod4Mask,               xK_bracketleft ), spawn "pidgin")
             ]
    myManageHook = manageDocks

--Key binding to toggle the gap for the bar.
--this is mod+ b
--http://hackage.haskell.org/packages/archive/X11/1.6.0/doc/html/Graphics-X11-Types.html
toggleStrutsKey XConfig {XMonad.modMask = modMask} = (modMask, xK_b)

--myKeys conf@(XConfig {XMonad.modMask = modm}) = M.fromList $
--    [ ((mod4Mask, xK_r), spawn "urxvt")
--    ]
