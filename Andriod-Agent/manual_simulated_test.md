# Manual Simulated Test
Dataset source: `mllmTeam/DroidCall`, converted deterministically into this repo's `android_intent` JSON schema.
The converter keeps only high-confidence single-step DroidCall rows and skips multi-step traces or rows needing unsupported nested/list extras.
Generated dataset size is 4,227 rows: 4,027 training rows and 200 eval rows.
Each SFT row uses TRL `prompt` / `completion` format, where completion is only the Android Intent JSON string.
Every generated completion was parsed back as JSON and validated against the Kotlin parser constraints.
Offline dataset validation result: 4,227 valid rows and 0 schema or semantic errors.
For Android-side validation, I sampled 100 rows from `train.jsonl` with seed `44`.
The sample was tested on connected emulator `emulator-5554`.
Instead of launching every operation destructively, the test used Android package-manager intent resolution.
This confirms Android can find an activity for the generated action/data/extras without creating alarms or repeatedly opening camera/SMS UIs.
Resolver report path: `data/sft/droidcall_android_intents/android_resolver_100.json`.
Resolver result: 100 sampled intents resolved, 0 unresolved.
Tested operation mix: 30 `VIEW` intents for contact/map/browser targets.
Tested operation mix: 9 dialer intents using `tel:` data URIs.
Tested operation mix: 8 image capture intents and 8 still-image camera intents.
Tested operation mix: 7 video capture intents and 6 video-camera intents.
Tested operation mix: 8 SMS draft intents using `smsto:` data URIs.
Tested operation mix: 7 timer intents and 6 alarm intents.
Tested operation mix: 4 show-alarms intents.
Tested operation mix: settings intents for display, security, wireless, date, Bluetooth, and input-method screens.
Representative Android handlers included DeskClock, Dialer, Camera2, Settings, Chrome, Maps, and ResolverActivity.
One tooling bug was found and fixed: `adb shell` needed remote command quoting for extras containing spaces.
Conclusion: this is a reasonable first Gemma 4 SFT seed dataset for Intent JSON generation.
Caveat: this validates activity resolution, not full end-to-end user confirmation or app-specific result return.
