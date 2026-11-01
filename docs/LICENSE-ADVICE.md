# License advice (a draft for discussion, not in effect)

This is not legal advice. It collects public sources and gives general suggestions. For decisions about publishing, commercial licensing, or anything that touches the teacher's work, talk to a lawyer or the university's legal office. No LICENSE file has been added, so the repository is still "all rights reserved" by default. Sources were read on 2026-11-01. Where something could not be checked it says "not verified".

## 0. Short answer

1. The license can be changed later. A sole copyright holder can pick any terms for new versions, and copies already handed out stay under the terms they came with. There is no LICENSE file today, so nobody holds a grant yet, which makes this the easiest moment to choose.
2. To say "others may not profit from this, I keep the right to profit" the closest fit is source available code under a non-commercial license, plus a separate commercial license on request. None of these licenses are open source in the OSI sense, and they should be called "source available".
3. Recommended: PolyForm Noncommercial 1.0.0 for the code, CC BY-NC-SA 4.0 for our own SGF structure, evaluation numbers and docs, and DCO plus a relicensing grant for outside contributions (a draft is in CONTRIBUTING.md).
4. The teacher's commentary text is not ours and we cannot license it. It has to stay outside every license above. The public repository currently holds long transcripts, so write a clear notice soon and, in the medium term, move the transcript text out of the public repo and keep only video links with time stamps.
5. Third party software (KataGo, yt-dlp, faster-whisper and so on) is only called, not shipped, so its distribution duties are mostly not triggered. They start the moment a binary, weight file or code copy goes into the repository, a release or an image.

## 1. What is in the repository and who holds the rights

| Content | Where | Rights holder (best reading) | Note |
|---|---|---|---|
| Viewer, pipeline, tools, remote batch scripts | `index.html`, `pipeline/`, `tools/`, `remote/` | The author | Can be licensed |
| Variation tree structure, KataGo evaluation numbers, how the key points are arranged | `data/sgf/`, non-transcript parts of `data/library.js` | The author (engine output plus the author's arrangement) | Can be licensed. Whether a bare sequence of Go moves is protected at all depends on the country, not verified |
| Teacher commentary (text after "teacher commentary" markers in the nodes) | The four filled SGF files (about 450 KB) and `data/library.js` | Chen Lintao (陈林涛), the speaker | Cannot be licensed by us. Transcribing and tidying does not move the copyright |
| Key points distilled from the spoken text | `pipeline/kp_*.json` and the matching nodes | Derived from the teacher's explanation, treat as derivative | Handle with the same care |
| Video list (titles, BV ids) | `data/sources/*/index.json` | Titles are short texts by the video authors, ids and links are facts | Low risk, not zero risk |
| Typo dictionary | `pipeline/fixdict.json` | The author | Can be licensed |

## 2. Can the license change later

Yes. The rules in practice:

- No LICENSE file means all rights reserved. Other people only have what the GitHub terms of service give them, which is viewing and forking a public repository inside GitHub. They have no right to use, change or redistribute the code ([choosealicense](https://choosealicense.com/no-permission/), [GitHub terms D.5](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)). Adding a license now only adds permissions, so nobody loses anything.
- While you are the only copyright holder you decide the license of future versions: stricter, looser, or dual.
- Versions and copies that were already handed out stay under the terms they came with. Creative Commons says plainly that its licenses cannot be revoked except against someone who breaks them. The licensor may stop distributing, but people who already have a copy may keep using it under the original terms ([CC FAQ](https://creativecommons.org/faq/)). Companies that change license usually apply the new terms to new releases only. HashiCorp's move of Terraform to the Business Source License is the well known example. Only a search summary was read for that one and the FAQ page itself did not show the answer text, so the wording is not verified.
- So loosening is always possible and tightening only works for future versions. That is a good reason to start with the stricter option: moving to MIT later needs only your own consent, while tightening later cannot reach people who already have an older copy.
- Outside contributors are the catch. Every contributor owns the copyright on what they contribute. GitHub's terms say that contributions to a repository with a license are licensed under that same license, unless a separate agreement says otherwise ([GitHub terms D.6](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)). If the repository uses PolyForm Noncommercial, contributors by default grant only that, and you could not hand their code to a commercial customer or switch the whole project to another license on your own. A CLA usually includes the right for the project to relicense. A DCO is only a sign-off that you may submit the work and does not give that right ([opensource.com](https://opensource.com/article/18/3/cla-vs-dco-whats-difference), [Kemitchell](https://writing.kemitchell.com/2021/07/02/DCO-Not-CLA)). Settle the mechanism before the first outside pull request is merged. The draft contribution terms in CONTRIBUTING.md do this. At the moment there is only one committer, so the problem does not exist yet.
- Your license only covers what you wrote. Libraries and tools you depend on keep their own licenses (section 5).
- If any part was written as part of a TUM course, internship or student research job, check who owns it first. A purely private hobby project normally has no such issue.

## 3. Options for "others may not profit, I keep the right to"

| Option | Meets the goal | Best for | OSI open source | Main risk |
|---|---|---|---|---|
| PolyForm Noncommercial 1.0.0 | Yes: use, modify and distribute are allowed, for non-commercial purposes only | Software | No | "Non-commercial" still has grey areas, and it is not a common sight on GitHub |
| CC BY-NC-SA 4.0 (or BY-NC 4.0) | Yes: attribution, non-commercial, derivatives under the same terms | Data, text, images | No (and not a software license) | Creative Commons itself advises against it for software, and the meaning of NC is disputed |
| Business Source License 1.1 | Partly: production use needs a commercial license, but it turns into open source on a set date | Commercial protection for server software | No | After at most four years others may use it commercially, which is the opposite of the goal |
| Custom "source visible, ask for a commercial license" (dual licensing) | Depends on the wording | Complete control | No | Writing your own terms invites loopholes, so avoid it without a lawyer |

### 3.1 PolyForm Noncommercial 1.0.0

It grants the right to use, change and distribute the software for non-commercial purposes. The text lists permitted cases: research, experiments and testing for public knowledge, personal study, private entertainment, hobby projects, and use by charities, schools and universities, public research bodies, safety and health organizations, environmental groups and government institutions, however they are funded ([SPDX page](https://spdx.org/licenses/PolyForm-Noncommercial-1.0.0.html), [source text](https://github.com/polyformproject/polyform-licenses/blob/1.0.0/PolyForm-Noncommercial-1.0.0.md)). It includes a patent license, requires anyone passing it on to include the terms (or their URL) and any `Required Notice:` lines you provide, lets a licensee who is told in writing about a violation recover by fixing it within 32 days, and does not allow sublicensing or transfer. It was drafted for software and has an SPDX identifier, `PolyForm-Noncommercial-1.0.0`. Commercial users have to come to you for a separate agreement, which is the dual licensing part.

### 3.2 CC BY-NC-SA 4.0 or BY-NC 4.0

Creative Commons advises against using its licenses for software, because they lack source code and patent terms and clash with the major software licenses. They suit documents, images and data ([CC FAQ](https://creativecommons.org/faq/)). Version 4.0 also licenses the EU database right on the same terms. You may offer a commercial license to others on the side, although a separate agreement binds only the parties who sign it. The SA part forces derivative datasets to stay BY-NC-SA, which supports your goal, while plain BY-NC does not.

The grey area of "non-commercial" is real:

- Germany: the Landgericht Köln (2014) held that a public broadcaster's website using a CC BY-NC picture was a commercial use. The Oberlandesgericht Köln (31 October 2014, 6 U 60/14) treated the CC license as standard terms, could not decide whether the use was commercial, and applied section 305c(2) of the BGB, which resolves doubt against the party who wrote the terms, here the licensor. On that point the broadcaster was therefore not in breach, although it lost on other points such as editing the picture and removing the name ([lhr-law summary](https://www.lhr-law.de/en/magazine-en/cologne-higher-regional-court-confirms-use-of-photographs-by-deutschlandradio-in-breach-of-cc-license-but-not-for-commercial-use/), [netzpolitik.org](https://netzpolitik.org/2014/der-dritte-streich-olg-koeln-zu-deutschlandradios-nutzung-cc-lizenzierter-fotos-mit-nc-modul/)). You live in Germany, so unclear NC wording may be read against you.
- United States: in Great Minds v. FedEx Office (Second Circuit, 2018) a copy shop copying course materials for school districts did not breach the NC term, because the licensed school districts were the ones exercising the rights ([CC legal database](https://legaldb.creativecommons.org/en/cases/15/)).

### 3.3 Business Source License 1.1

Source is public, non-production use is free and production use needs a commercial license unless the additional use grant allows it. The license converts automatically to an open source license compatible with GPL v2 or later on a change date that is at most four years after the first public release. MariaDB's own FAQ says the BSL is not an open source license ([MariaDB BSL FAQ](https://mariadb.com/bsl-faq-adopting/)). Others may use the code commercially after the conversion, which conflicts with your goal, and it was designed to protect server software against commercial competitors, so "production use" has no clear meaning for an offline study resource. Not recommended.

### 3.4 Custom terms and dual licensing

The safest way is to publish under an existing non-commercial license (3.1 or 3.2) and sign a separate commercial contract when someone asks. Put one sentence in the README, such as "for commercial use please get in touch". Do not rewrite the terms yourself. How people reach you is up to you. A GitHub issue or a message works if you do not want to publish an email address.

### 3.5 Are they open source, and what follows

None of them is. The Open Source Definition forbids discrimination against persons or groups (point 5) and against fields of endeavor, which explicitly includes commercial use (point 6) ([OSD](https://opensource.org/osd)). Consequences:

- Do not call it "open source". Say source available.
- Some companies, Linux distributions and foundations will not accept such code, and outside contributors may be fewer.
- Others cannot merge your code into an MIT or GPL project and republish it.
- How GitHub displays a PolyForm license (whether it detects it) is not verified.

### 3.6 GitHub forks and display

The GitHub terms say that making a repository public allows others to view it and to fork it on GitHub. That right does not depend on your license, so a license cannot forbid forking a public repository on GitHub ([terms D.5](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)). A license governs what people may do with a fork afterwards. To prevent forking, make the repository private.

### 3.7 Vague "non-commercial" and the cost of enforcing it

Grey cases include a personal blog with ads, internal use by a company's staff, a paid training course, and a sponsored community. PolyForm lists permitted users and uses in more detail than CC and is less ambiguous, but the border still needs interpretation. The German case above shows how unclear wording can be read. A single maintainer will find it hard to notice and pursue misuse, so a license mostly works as a clear statement and something to point to in a dispute. It does not stop anyone technically.

## 4. Recommendation

| Content | License | Reason |
|---|---|---|
| Code: `index.html`, `pipeline/`, `tools/`, `remote/`, the parts of `engine-config/` that we wrote | PolyForm Noncommercial 1.0.0 with a line `Required Notice: Copyright (c) 2026 Xtraordinaire9911` (use the GitHub name, not a real name or email) | Written for software, names personal study, research and education as allowed, so Go hobbyists are covered, and commercial users have to ask you |
| Our SGF variation structure, evaluation numbers, own docs (`README`, `docs/`) | CC BY-NC-SA 4.0, limited to "the original parts of this project" and explicitly excluding the teacher's commentary | Standard for data and text, SA keeps derivative datasets non-commercial, 4.0 covers database rights |
| The teacher's commentary and key points taken from it | Not licensed. State that the rights belong to Chen Lintao and that no license of this project covers it | We are not the rights holder and cannot grant anything |
| Video list (titles, BV ids, links) | Keep, with the source named | Facts and links, low risk |
| Outside contributions | DCO plus a relicensing grant (draft in CONTRIBUTING.md) | Keeps the option of commercial licensing and of changing the license later |

If one license for everything (minus the teacher's text) is easier, PolyForm Noncommercial for the whole repository works, but it is worse for data and docs, and whether "software" covers plain data files is not verified. The split above is the better fit.

Files you would add when you decide (none of them exist yet):

- `LICENSE` with the full PolyForm Noncommercial 1.0.0 text and the `Required Notice:` line.
- `LICENSE-DATA.md` with CC BY-NC-SA 4.0 and the exclusion for the teacher's text.
- `NOTICE.md` with the third party list (section 5), the teacher notice and a takedown contact.
- Optionally `SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0` at the top of source files.
- A README license paragraph, for example: "Code: PolyForm Noncommercial 1.0.0. Data and docs, except the teacher's commentary: CC BY-NC-SA 4.0. The commentary comes from public videos by Chen Lintao, the copyright belongs to the author, and it is not covered by these licenses. For commercial use please get in touch. This project is source available, not open source."

### 4.1 What to do about the teacher's commentary

The commentary is a transcript of what he says in the videos. Transcribing and tidying is copying and adapting someone else's work, and the copyright stays with him. The transcripts in the repo are close to word for word and go far beyond a short quotation.

The legal points, in general terms (check the official texts and ask a lawyer):

- China: oral works are a protected category (Copyright Law, Article 3). The two common fair use cases are using a published work for personal study, research or appreciation, and quoting appropriately to introduce or comment on a work. Both need the author's name and the title of the work to be given, must not interfere with normal use, and must not unreasonably harm the owner's rights (Article 24). Making a work available to the public over an information network is a separate exclusive right (Article 10). Publishing a full transcript on GitHub is not personal study ([National People's Congress](http://www.npc.gov.cn/npc/c30834/202011/848e73f58d4e4c5b82f69d25d46048c6.shtml), checked against the [copyright administration's copy](https://www.ncac.gov.cn/xxfb/flfg/flfg_532/202103/t20210309_50530.html)).
- Germany: copies made for private use may neither be distributed nor used for public reproduction (section 53(6) UrhG). The research text and data mining rule (section 60d) only lets you share with a clearly limited group for joint research or for checking quality, and public access must end afterwards. The general text and data mining rule (section 44b) requires copies to be deleted once no longer needed, and right holders can reserve their rights. The right to quote (section 51) is limited to what the purpose of quoting justifies ([section 53](https://www.gesetze-im-internet.de/urhg/__53.html), [section 60d](https://www.gesetze-im-internet.de/urhg/__60d.html), [section 51](https://www.gesetze-im-internet.de/urhg/__51.html), [commentary on 44b](https://cms.law/de/deu/legal-updates/text-und-data-mining-nach-dem-neuen-urheberrecht)). None of these allow publishing a full transcript.
- The README sentence "we will remove it immediately if the author asks" is polite, but it is not permission and does not replace a license.
- Whether the Bilibili terms of use say anything about transcription or downloading: not verified.

Suggestions, from light to heavy, which can be combined:

1. Right away and free: state in the README and in `NOTICE.md` that the teacher's commentary does not belong to this project and is not covered by any license, and never describe the whole repository as being under one license.
2. Medium term, recommended: split. The public repo keeps the variation tree, the evaluations, video links with time stamps, and key points you wrote in your own words. The transcript text lives in a private data repository or only on your machine, and the viewer loads it as an optional local file (for example `data/private/library.private.js`), which needs changes in `pipeline/` and `index.html` on a separate feature branch. Key points distilled from the transcript are still derived from it, so either keep them private too or rewrite them in your own words with the source named.
3. Ask Chen Lintao (a private message on Bilibili) for written permission. State what you need: whether the transcript may be public, whether non-commercial study use is fine, and how to credit him. This is the cleanest route. Keep the conversation.
4. History: the published v0.1 commit, the release and any forks or clones still contain the text, and deleting files only affects new versions. Removing it completely means rewriting git history and force pushing, which affects every clone. That is a big step and has not been done. Consider it if the author objects or when you do the split.
5. Using the text on your own machine for your own study is fine.

## 5. Third party software and weights: what distribution requires

This repository only calls or imports the tools below. It contains none of their code, binaries or weights, so their distribution duties are mostly not triggered. They begin when a copy goes into the repo, a GitHub release, a Colab or Kaggle dataset or a public image.

| Component | License | How it is used here | When shipping it | Source |
|---|---|---|---|---|
| KataGo program | MIT style. Third party parts in `cpp/external` (CLBlast, cutlass, nlohmann_json and others) have their own licenses | Runs `katago.exe` or the Linux build as a process | Keep the copyright and permission notice, and for binaries the licenses of the bundled third party parts | [KataGo LICENSE](https://github.com/lightvector/KataGo/blob/master/LICENSE) |
| KataGo weights (local file `kata1-tf3-b11c768-s12752M-d6531M.bin.gz`) | "KataGo Neural Network License", permissive (use, copy, modify, distribute, sell) with the copyright and permission notice kept. It covers the official kata1 networks and extra networks labelled KataGo. Extra networks from other contributors may have no stated terms. The g170 networks are CC0 | Read from disk locally or in the cloud, not committed | Include the notice. Which group this exact file belongs to was not verified, please check where you downloaded it | [network license](https://katagotraining.org/network_license/), [network list](https://katagotraining.org/networks/) |
| KataGo analysis output (scores, winrates) | The MIT style terms that were read do not restrict output, but the full text was not compared word by word | Written into SGF and `a2.json` | none known | same |
| yt-dlp | The source is under the Unlicense. Release binaries built with PyInstaller include GPLv3+ code | `python -m yt_dlp` downloads the videos | Nothing when only used locally. Shipping its binary or an image that contains it brings the GPL duties | [yt-dlp README](https://github.com/yt-dlp/yt-dlp) |
| faster-whisper | MIT | Speech to text | Keep the notice | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) |
| Whisper code and weights | MIT, as stated by the OpenAI repository | The `small` model | Keep the notice. The license of the converted faster-whisper weights follows their Hugging Face model card, not verified | [openai/whisper](https://github.com/openai/whisper) |
| CTranslate2 (faster-whisper backend) | Not verified | Indirect dependency | | |
| numpy | BSD-3-Clause | `board.py`, `tr.py` | Keep the notice | [numpy license](https://numpy.org/doc/stable/license.html) |
| ffmpeg | LGPL or GPL depending on the build, which one is used was not verified | External program started with `subprocess` | Nothing unless you ship it | |
| OpenCV | The README mentions OpenCV for board recognition, but no import of `cv2` was found in `pipeline/`, so the README may be out of date. License details not verified | | | |
| Frontend libraries, fonts, CDNs | `index.html` is a single file. The reference check found only `data/library.js` | | None | repository check |

If a release ever carries a KataGo binary, weights or a packaged yt-dlp, put the matching license texts in `NOTICE.md`, and for GPL parts say where the source can be obtained.

## 6. One paragraph on China and Germany or the EU

Chinese copyright law protects oral works, and its fair use cases are limited to personal study or research and appropriate quotation with attribution. German and EU private copy and text and data mining exceptions do not allow publishing someone else's full transcript either. You publish from Munich, so German law mainly applies to what you do there, and rights in the country of origin (China) can matter as well. Which law applies and whether something infringes is a question for a lawyer or the university's legal office, so please do not rely on this note alone.

## 7. Next steps (all yours, none done here)

1. Decide on section 3.1 and section 4 (suggested: PolyForm Noncommercial for code, CC BY-NC-SA for data and docs, a separate notice for the teacher's text).
2. Add the teacher notice to the README and `NOTICE.md` first (section 4.1, point 1).
3. Decide whether to contact Chen Lintao and whether to split off a private data repository.
4. Confirm the contribution terms in `CONTRIBUTING.md`, or replace them with a proper CLA, before merging an outside pull request.
5. Have a lawyer or the university legal office read the important decisions.
6. Find out where `kata1-tf3-b11c768-...` came from and which license it carries.
7. When decided, add the LICENSE files on a branch of their own following `docs/WORKFLOW.md` and write it up in the changelog.

## Not verified

- How different countries treat a bare sequence of Go moves or a variation tree.
- The original text of HashiCorp's license FAQ (only a search summary was read).
- How GitHub detects and displays PolyForm.
- Which KataGo network family `kata1-tf3-b11c768-...` belongs to and which license applies, plus the exact wording of the KataGo license on outputs.
- Licenses of CTranslate2, the ffmpeg build in use, OpenCV and the converted faster-whisper weights.
- What the Bilibili terms of use say about transcription and downloads.
- Chinese statute: the official site of the National People's Congress could not be opened from the tool used (the connection failed), so article numbers follow the copy on the copyright administration's site.

## Sources (visited 2026-11-01)

- choosealicense, the default without a license: https://choosealicense.com/no-permission/
- GitHub terms of service (D.5 view and fork, D.6 contributions under the repository license): https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
- PolyForm Noncommercial 1.0.0: https://spdx.org/licenses/PolyForm-Noncommercial-1.0.0.html and https://github.com/polyformproject/polyform-licenses/blob/1.0.0/PolyForm-Noncommercial-1.0.0.md
- Creative Commons FAQ (software, irrevocability, dual licensing, database rights): https://creativecommons.org/faq/
- Open Source Definition: https://opensource.org/osd
- BSL 1.1 FAQ: https://mariadb.com/bsl-faq-adopting/
- DCO and CLA: https://opensource.com/article/18/3/cla-vs-dco-whats-difference, https://writing.kemitchell.com/2021/07/02/DCO-Not-CLA, DCO text https://developercertificate.org/
- German NC case law: https://www.lhr-law.de/en/magazine-en/cologne-higher-regional-court-confirms-use-of-photographs-by-deutschlandradio-in-breach-of-cc-license-but-not-for-commercial-use/ and https://netzpolitik.org/2014/der-dritte-streich-olg-koeln-zu-deutschlandradios-nutzung-cc-lizenzierter-fotos-mit-nc-modul/
- Great Minds v. FedEx Office: https://legaldb.creativecommons.org/en/cases/15/
- Chinese Copyright Law (2020 amendment): http://www.npc.gov.cn/npc/c30834/202011/848e73f58d4e4c5b82f69d25d46048c6.shtml and https://www.ncac.gov.cn/xxfb/flfg/flfg_532/202103/t20210309_50530.html
- German UrhG sections 51, 53, 60d: https://www.gesetze-im-internet.de/urhg/__51.html, https://www.gesetze-im-internet.de/urhg/__53.html, https://www.gesetze-im-internet.de/urhg/__60d.html. Commentary on section 44b: https://cms.law/de/deu/legal-updates/text-und-data-mining-nach-dem-neuen-urheberrecht
- KataGo: https://github.com/lightvector/KataGo/blob/master/LICENSE and https://katagotraining.org/network_license/
- yt-dlp https://github.com/yt-dlp/yt-dlp, faster-whisper https://github.com/SYSTRAN/faster-whisper, Whisper https://github.com/openai/whisper, numpy https://numpy.org/doc/stable/license.html
