# Daily call prep delivery

## Window and reads

- Run multi-call window mode for every external call today in `policy.momentum.display_tz`.
  External attendees are defined by `policy.tooling.internal_domains`. Preserve all existing read-only brief and source checks.
- Read Momentum with curl and the authorized runtime credential selected through the org call-transcript skill.
  Verify the configured curl and proxy behavior. If the credential fails to resolve, refresh the current credential listing once and retry the same curl with the same handle.
  Never copy handles, secrets, or customer evidence into Git. An unavailable credential is not checked, not absent transcript evidence.
- If complete Calendar reads find no external calls today, reply in one line and run `pplx automation suppress-run-notification`. Generate no audio.

## Audio

1. Finish the full written summary first. Load the media skill and its speech guide.
2. Narrate the full summary, not a shorter recap. Preserve every call, substantive fact, commitment, risk, discovery gap, CRM note, hypothesis label, and evidence limitation.
3. Adapt headings, dates, times, acronyms, and field labels for natural speech. Do not read raw URLs, record IDs, or Markdown syntax aloud.
   Keep citations in the written summary and use short source names in narration where needed.
4. Read `audio` settings from the `call_prep` policy block for `voice` and `filename`. Missing settings are an audio failure, never an invented default.
   Use that one calm professional voice without music. If the script exceeds the input limit, split at section or sentence boundaries.
   Generate every part with the same voice and join them in order into one MP3 without changing playback speed.
5. Format the configured filename with the local ISO date. Verify every section is included, playback works, and the ending is not cut off.
6. Attach one playable downloadable MP3 alongside the original written summary in the run thread. Preserve existing push delivery, without a duplicate notification.
   Keep script and audio files in the sandbox, never Git or Project Files. If generation fails, deliver the written brief and explicitly report the audio failure.
