import XMonad

import XMonad.Util.EZConfig
import XMonad.Util.Ungrab

main :: IO ()
main = xmonad $ def
    { modMask = mod4Mask -- remap modifier key from alt to super.
    }
  `additionalKeysP`
    [ ("M-f", spawn "firefox"),
      ("M-b", spawn "brave"),
      ("M-c", spawn "code")
    ]
