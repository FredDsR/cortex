# Changelog

## [0.2.3](https://github.com/FredDsR/cortex/compare/v0.2.2...v0.2.3) (2026-09-11)


### Documentation

* add PyPI, CI, and license badges to the README ([#74](https://github.com/FredDsR/cortex/issues/74)) ([57fb8d7](https://github.com/FredDsR/cortex/commit/57fb8d7c88500034f40421433178e306cc6214d0))

## [0.2.2](https://github.com/FredDsR/cortex/compare/v0.2.1...v0.2.2) (2026-09-09)


### Documentation

* use absolute image URLs so the README renders on PyPI ([#72](https://github.com/FredDsR/cortex/issues/72)) ([a85453b](https://github.com/FredDsR/cortex/commit/a85453b127f6c7d80543da51ed71b9b75c03ab60))

## [0.2.1](https://github.com/FredDsR/cortex/compare/v0.2.0...v0.2.1) (2026-09-09)


### Bug Fixes

* **ci:** release 0.2.1 and document the PyPI filename trap ([#70](https://github.com/FredDsR/cortex/issues/70)) ([69880b5](https://github.com/FredDsR/cortex/commit/69880b53b8d775a97b207df6e429ae25520f8dd5))

## [0.2.0](https://github.com/FredDsR/cortex/compare/v0.1.0...v0.2.0) (2026-09-09)


### Features

* --project flag on install.sh for repo-scoped skill install ([ffbe8c3](https://github.com/FredDsR/cortex/commit/ffbe8c3fdc5fcec9cb39091585b51a1b8b8ca027))
* add .claude-plugin manifests for /plugin marketplace compatibility ([8a67c26](https://github.com/FredDsR/cortex/commit/8a67c26c53dc4e13b579f6dd977acb1fcebdcdb8))
* add .gitignore template for ~/.work/ ([eef1b98](https://github.com/FredDsR/cortex/commit/eef1b98e627a7262dea94af847cf014aabf5cd90))
* add bootstrap.sh for one-line curl install ([ae7ea91](https://github.com/FredDsR/cortex/commit/ae7ea9149a35b6dddfd9c67f1537a127895c5c47))
* add commit_push.sh with tests; init bare remotes with main branch ([99977be](https://github.com/FredDsR/cortex/commit/99977be3e3852fcc63dea398b6249e2f9485a6cb))
* add is_enabled.sh state gate with tests ([eeaf996](https://github.com/FredDsR/cortex/commit/eeaf996b2e423e5712ec06dc265b0f10bca7e177))
* add pull.sh with SUMMARY auto-resolve and task-conflict surfacing ([c8fc7ed](https://github.com/FredDsR/cortex/commit/c8fc7ed136b6d5d62bc472748f07a193ae8daa28))
* add setup.sh with --skip/--clone/--init paths and tests ([703043c](https://github.com/FredDsR/cortex/commit/703043c9ffe6765655c7dab4fe3f686743f8b141))
* add tracking-work-kb skill for authoring knowledge/workbench ([#8](https://github.com/FredDsR/cortex/issues/8)) ([e55f580](https://github.com/FredDsR/cortex/commit/e55f5803367155b8d441ffc75b169f3eef335ec3))
* add uninstall.sh with round-trip tests ([8fca0f1](https://github.com/FredDsR/cortex/commit/8fca0f190924f3b20d62f018990173273480e14b))
* add update-skills.sh wrapper for one-shot pull + install ([8cd7981](https://github.com/FredDsR/cortex/commit/8cd79811b542234901355dde7102e21de55de383))
* **cortex:** opt-in session-start injection ([#22](https://github.com/FredDsR/cortex/issues/22)) ([d478d1f](https://github.com/FredDsR/cortex/commit/d478d1fcce67e598fd935ab67f9d6dccdc07f761))
* **cortex:** Python engine Phase 1 - shared core (frontmatter + store) ([#16](https://github.com/FredDsR/cortex/issues/16)) ([ac3b326](https://github.com/FredDsR/cortex/commit/ac3b3260f82b1cb7ee3c8bd79f6dc6bdc65c0c56))
* **cortex:** Python engine Phase 2 - kb (new/update/index/ingest), retire bash work-kb ([#17](https://github.com/FredDsR/cortex/issues/17)) ([97bc8d0](https://github.com/FredDsR/cortex/commit/97bc8d087ee17f14a2df814dc5314511d3a86b90))
* **cortex:** Python engine Phase 3 - viz under the engine, drop work_viz ([#18](https://github.com/FredDsR/cortex/issues/18)) ([c66bc09](https://github.com/FredDsR/cortex/commit/c66bc09fb99f94e483e4f4ee1789233e6b992da9))
* **cortex:** Python engine Phase 4 - query neighbors ([#19](https://github.com/FredDsR/cortex/issues/19)) ([db29c89](https://github.com/FredDsR/cortex/commit/db29c89a453d004a6c1187d6dc4d1d8602435874))
* **cortex:** Python engine Phase 5 - migrate + cleanup ([#20](https://github.com/FredDsR/cortex/issues/20)) ([9e66746](https://github.com/FredDsR/cortex/commit/9e66746b1b09456fad4c92a1942634f6475a3ba1))
* **cortex:** unified cortex CLI + product rename + KB frontmatter migration ([#15](https://github.com/FredDsR/cortex/issues/15)) ([d2beca9](https://github.com/FredDsR/cortex/commit/d2beca9022302f26f37ad1ce600b46870522769d))
* **kb:** add cortex kb lint, the missing third operation ([#30](https://github.com/FredDsR/cortex/issues/30)) ([#45](https://github.com/FredDsR/cortex/issues/45)) ([7421109](https://github.com/FredDsR/cortex/commit/74211090254efc4ef16ba2bae408e5b0dd0401fe))
* **kb:** derive an OKF section 9 change log from git ([#51](https://github.com/FredDsR/cortex/issues/51)) ([#60](https://github.com/FredDsR/cortex/issues/60)) ([e24c3fa](https://github.com/FredDsR/cortex/commit/e24c3fae4b99e8282935f2a63b440227163f231e))
* **kb:** make Gotcha canonical and stop the type vocabulary drifting ([#56](https://github.com/FredDsR/cortex/issues/56)) ([bf32e8e](https://github.com/FredDsR/cortex/commit/bf32e8e9769293299b380fc3e5536dbf9bf8d190))
* **kb:** make Gotcha canonical and stop the vocabulary drifting ([bf32e8e](https://github.com/FredDsR/cortex/commit/bf32e8e9769293299b380fc3e5536dbf9bf8d190))
* **kb:** make the knowledge store a conformant OKF bundle ([#50](https://github.com/FredDsR/cortex/issues/50)) ([#55](https://github.com/FredDsR/cortex/issues/55)) ([bed6cc6](https://github.com/FredDsR/cortex/commit/bed6cc6d315fa6f5890cc41b1744ff20f49a81e6))
* **kb:** structured knowledge frontmatter + work-kb index ([#13](https://github.com/FredDsR/cortex/issues/13)) ([f5b85da](https://github.com/FredDsR/cortex/commit/f5b85da2a4f933a8dda568721157c3b99e04603a))
* **kb:** work-kb ingest (bulk codebase -&gt; knowledge) ([#14](https://github.com/FredDsR/cortex/issues/14)) ([1a96c25](https://github.com/FredDsR/cortex/commit/1a96c251fe0adecbe3aef8f0ac5312d46cfc5a85))
* monorepo all four tracking-work skills with harness-agnostic install.sh ([f4d3a85](https://github.com/FredDsR/cortex/commit/f4d3a85d45e87ce703581617506343e58cea766f))
* **okf:** export and import, translating links at the boundary ([#53](https://github.com/FredDsR/cortex/issues/53)) ([#62](https://github.com/FredDsR/cortex/issues/62)) ([d5d4880](https://github.com/FredDsR/cortex/commit/d5d4880cf0a6e34119488efba2d231338986df75))
* package cortex for PyPI with a src layout and release pipeline ([#66](https://github.com/FredDsR/cortex/issues/66)) ([8768979](https://github.com/FredDsR/cortex/commit/876897987c5e37fd4edcc02b4450e5e8508534fa))
* **query:** BM25 keyword search over knowledge and tasks, fused with RRF ([#31](https://github.com/FredDsR/cortex/issues/31)) ([#46](https://github.com/FredDsR/cortex/issues/46)) ([1c05f97](https://github.com/FredDsR/cortex/commit/1c05f97377e27879e8b1b83a72aec70039d64c63))
* **query:** cortex query related, doc-as-query BM25 links ([#52](https://github.com/FredDsR/cortex/issues/52)) ([#54](https://github.com/FredDsR/cortex/issues/54)) ([422614a](https://github.com/FredDsR/cortex/commit/422614a96796fc23323bb693f8f063f374211906))
* **skills:** manifest, session_start, frontmatter migration ([6e30a7a](https://github.com/FredDsR/cortex/commit/6e30a7ae8f8f8ddb1fcd9b2945d588aa543f0a68))
* the brain - cross-workspace knowledge dictionary ([#23](https://github.com/FredDsR/cortex/issues/23)) ([921c2ca](https://github.com/FredDsR/cortex/commit/921c2cac0520d0dbb9494c4df5b32fe11a259664))
* tracking-work-viz browser viewer for ~/.work/ ([00c115f](https://github.com/FredDsR/cortex/commit/00c115fc2021b940578c64edf45f3b3a93670a01))
* **tracking-work-viz:** add --out-dir flag for static + serve modes ([0ec8d19](https://github.com/FredDsR/cortex/commit/0ec8d19bf9105b8af1411fb7b625c12ff2ec97fe))
* **tracking-work:** Close the Day routine + /tracking-work:close-day ([#10](https://github.com/FredDsR/cortex/issues/10)) ([d610cc0](https://github.com/FredDsR/cortex/commit/d610cc04806389ff3907f4becad87e00795119c3))
* **viz:** [[ wikilink picker + reverse-grammar (layer 2) ([#12](https://github.com/FredDsR/cortex/issues/12)) ([bb8c1ae](https://github.com/FredDsR/cortex/commit/bb8c1ae4d59655bc1a67d4e8bdce57f4ded7536a))
* **viz:** distinct shapes + orbit depth for knowledge and workbench ([#9](https://github.com/FredDsR/cortex/issues/9)) ([076b12b](https://github.com/FredDsR/cortex/commit/076b12b398ae6b87856cd4c7527bac9bf2a07c13))
* **viz:** green checkmark badge for resolved tasks ([#5](https://github.com/FredDsR/cortex/issues/5)) ([c7be683](https://github.com/FredDsR/cortex/commit/c7be683bce6655b15672f0cfd921e214b587db85))
* **viz:** in-browser edit surface (serve --edit) ([#11](https://github.com/FredDsR/cortex/issues/11)) ([8f116a4](https://github.com/FredDsR/cortex/commit/8f116a4994a9cf64260f268e97f5fecaa871e661))
* **viz:** rename memory node kind to knowledge ([#6](https://github.com/FredDsR/cortex/issues/6)) ([19fdfc0](https://github.com/FredDsR/cortex/commit/19fdfc034f85bfdcf4b1fffa377366b3bf8e75eb))
* **viz:** render author H/A badge on knowledge/workbench nodes ([#7](https://github.com/FredDsR/cortex/issues/7)) ([a87b1f7](https://github.com/FredDsR/cortex/commit/a87b1f7a0b175a3c3fe73348c4e12732a4d69b98))
* **viz:** show-archived toggle ([#3](https://github.com/FredDsR/cortex/issues/3)) ([6d56272](https://github.com/FredDsR/cortex/commit/6d562726ac501554821eff1ccd94456ed9716d89))
* **viz:** show-archived toggle ([#4](https://github.com/FredDsR/cortex/issues/4)) ([a794952](https://github.com/FredDsR/cortex/commit/a794952f6ac7097755c16b70359cb7b0aba4e4e7))
* **viz:** world search - global fuzzy search on every page ([#21](https://github.com/FredDsR/cortex/issues/21)) ([75cf9a7](https://github.com/FredDsR/cortex/commit/75cf9a7d59e1cf75b01ea247905df7dacebd1134))


### Bug Fixes

* **ci:** point release-please at the real version file ([#67](https://github.com/FredDsR/cortex/issues/67)) ([7d27467](https://github.com/FredDsR/cortex/commit/7d27467f176edbafd190110245bbfdbae3114868))
* **ci:** tag releases as v0.2.0, not agentic-cortex-v0.2.0 ([#69](https://github.com/FredDsR/cortex/issues/69)) ([3c51539](https://github.com/FredDsR/cortex/commit/3c515394c2154d404134d624167b35c7821eeabe))
* **cortex:** resolve workspace from .meta cwd ([f5aee44](https://github.com/FredDsR/cortex/commit/f5aee44ec105cea365a8f3260ff68efb709afb1b))
* **ingest:** sanitize extracted text before it reaches injection ([#44](https://github.com/FredDsR/cortex/issues/44)) ([605b8f4](https://github.com/FredDsR/cortex/commit/605b8f4e69053a0745af5e4b70f174996f2221d7))
* **kb:** preserve unrecognized frontmatter keys through kb update ([#42](https://github.com/FredDsR/cortex/issues/42)) ([ec31713](https://github.com/FredDsR/cortex/commit/ec317133dbc8a49f0653f253f6e23db9f6747537))
* make every store write atomic ([#34](https://github.com/FredDsR/cortex/issues/34)) ([#41](https://github.com/FredDsR/cortex/issues/41)) ([a525220](https://github.com/FredDsR/cortex/commit/a52522029a9f99a735fa8724057979a6ca195dfc))
* **store:** contain workspace/session tokens to the store root ([#43](https://github.com/FredDsR/cortex/issues/43)) ([c94c6d1](https://github.com/FredDsR/cortex/commit/c94c6d15016f46c6ad9cb0de33e8f244f892cde6))
* **store:** say what --workspace all left out ([#47](https://github.com/FredDsR/cortex/issues/47)) ([#49](https://github.com/FredDsR/cortex/issues/49)) ([a0fc7b5](https://github.com/FredDsR/cortex/commit/a0fc7b5e89d382e6a7646b789b7369e315d2e79b))
* **sync:** rebase-and-retry on push rejection in commit_push.sh ([#24](https://github.com/FredDsR/cortex/issues/24)) ([70862a6](https://github.com/FredDsR/cortex/commit/70862a61143db392f73af3d61ba37ca33e1f038c))
* **viz:** normalize SUMMARY frontmatter keys to Title Case ([ea9c321](https://github.com/FredDsR/cortex/commit/ea9c3212454e09d9286fd25610e49ba5fc4f9776))


### Refactoring

* **cli:** split kb, inject, and sync into packages ([#57](https://github.com/FredDsR/cortex/issues/57)) ([#65](https://github.com/FredDsR/cortex/issues/65)) ([529698f](https://github.com/FredDsR/cortex/commit/529698f5f170693b50283a16bed30554bfe3109e))
* **cli:** split search.py and ingest.py along the CLI seam ([#57](https://github.com/FredDsR/cortex/issues/57)) ([#63](https://github.com/FredDsR/cortex/issues/63)) ([9d628d0](https://github.com/FredDsR/cortex/commit/9d628d0ff91bf748c1892f8865250d9f9a39698a))
* **kb:** split lint.py into checks, fix, and cli ([#57](https://github.com/FredDsR/cortex/issues/57)) ([9aa32b0](https://github.com/FredDsR/cortex/commit/9aa32b06b095851b8d32addf59d77d4dec402bc8))
* **kb:** split lint.py into checks, fix, and cli ([#57](https://github.com/FredDsR/cortex/issues/57)) ([#61](https://github.com/FredDsR/cortex/issues/61)) ([9aa32b0](https://github.com/FredDsR/cortex/commit/9aa32b06b095851b8d32addf59d77d4dec402bc8))
* **skills:** trim SKILL.md prose, dedup, skip stale .meta writes ([e12cee8](https://github.com/FredDsR/cortex/commit/e12cee833d200188ce8b9947e8d251ceec64aebb))
* **viz:** split generator.py into layout, pages, and graph ([#58](https://github.com/FredDsR/cortex/issues/58)) ([b5e623f](https://github.com/FredDsR/cortex/commit/b5e623faabc25bba86d0f1ada1d6bbc0aa3e0d84))


### Documentation

* add SKILL.md describing invocation and contracts ([a31bdce](https://github.com/FredDsR/cortex/commit/a31bdce9329647f99230cdf4cceeec609ff97b32))
* add usage guide, concepts, and mermaid diagrams ([#29](https://github.com/FredDsR/cortex/issues/29)) ([c53dd9f](https://github.com/FredDsR/cortex/commit/c53dd9f705948e9f80cd4c5dc49aba9a4b6e7dc4))
* add viz dashboard screenshots (light + dark) to README ([#26](https://github.com/FredDsR/cortex/issues/26)) ([5380614](https://github.com/FredDsR/cortex/commit/538061495a4514661bd5e68bf12dbb607a59d986))
* bring SKILL.md and READMEs in line with shipped tracking-work-viz ([1c3cc2f](https://github.com/FredDsR/cortex/commit/1c3cc2f12fed923b2e8bd6b665bcd6f4be55a739))
* drop the tracking-work upgrade section ([fecfc8b](https://github.com/FredDsR/cortex/commit/fecfc8bbc2782a5ba06fe34ae37faf75e32ae1e2))
* **readme:** lead with the llm-wiki comparison ([#48](https://github.com/FredDsR/cortex/issues/48)) ([9e61121](https://github.com/FredDsR/cortex/commit/9e61121cc05351168f0b8c8be07150243477a9b1))
* show both light and dark viz screenshots explicitly ([#27](https://github.com/FredDsR/cortex/issues/27)) ([d0a27ca](https://github.com/FredDsR/cortex/commit/d0a27caea5f24ffd7f5623635b27fa0775bcf13d))
* **skills:** document viz/ in sync gitignore + cross-link from viz ([d74d2d8](https://github.com/FredDsR/cortex/commit/d74d2d8e76b671c257e8745b2d22c90cb9b615b1))
* snapshot of modified main tracking-work SKILL.md ([578fd78](https://github.com/FredDsR/cortex/commit/578fd78760e97f0a7d3995185fa0f52d98d43fb9))
* use neutral clone path in README install instructions ([8285a63](https://github.com/FredDsR/cortex/commit/8285a63ac1c5d96b74f0939b05aa727adb9602c7))

## Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
