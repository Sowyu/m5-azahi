# Publication workflow

User-authorized destination: `Sowyu/m5-azahi`. This public source publication
supersedes the earlier no-commits preference for this project.

Use a separate public clone. Export only an explicit reviewed file allowlist;
never run `git add .` in the private bring-up workspace. Before each commit:

1. Update the public status and handoff, distinguishing build/test/live evidence.
2. Export relevant source changes and reapply privacy/safety transformations.
3. Review every added path and scan for private paths, device identifiers,
   credentials, network addresses, images, binary payloads and recovery data.
4. Run applicable host-only tests, inspect the staged diff, commit and push.
5. Verify the remote commit. Do not force-push or publish directly from captures.

This is a development workflow, not an unattended background uploader.

## Intentionally excluded

- Apple firmware, kernelcache/DriverKit caches, raw ADTs and device dumps.
- Kernel/initrd/rootfs/boot images, compiled modules, archives and downloaded SDKs.
- Photos, webcam/audio captures, chat history and raw logs.
- Recovery backups, LocalPolicy/boot manifests, receipts containing identifiers.
- ECIDs, device serial numbers, private APFS/Linux UUIDs, personal absolute paths,
  authentication material and LAN endpoints.
- Machine-pinned Recovery installers, delivery servers and session-specific
  proxy mutation scripts. Public notes describe outcomes without exposing pins.
- Unreviewed historical probes and complete upstream checkouts.

The current snapshot covers core input/storage/USB source, selected packaging
tools and public handoff notes. It is not a byte-for-byte backup of the private
workspace. Additional historical source can be published after review.
