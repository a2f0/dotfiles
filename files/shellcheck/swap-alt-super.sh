#!/bin/sh
set -eu

# Swap Alt/Option and Super/Command keys on macOS using hidutil.
# Run this after plugging in a PC keyboard or after reboot.

hidutil property --set '{
  "UserKeyMapping": [
    {
      "HIDKeyboardModifierMappingSrc": 30064771298,
      "HIDKeyboardModifierMappingDst": 30064771299
    },
    {
      "HIDKeyboardModifierMappingSrc": 30064771299,
      "HIDKeyboardModifierMappingDst": 30064771298
    },
    {
      "HIDKeyboardModifierMappingSrc": 30064771302,
      "HIDKeyboardModifierMappingDst": 30064771303
    },
    {
      "HIDKeyboardModifierMappingSrc": 30064771303,
      "HIDKeyboardModifierMappingDst": 30064771302
    }
  ]
}'
