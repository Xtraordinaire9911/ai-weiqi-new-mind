# 许可证决定与背景 / License decision and background

这不是法律意见,只是整理了公开资料并给出一般性建议。涉及公开发布、商业授权,或者任何牵涉老师作品的决定,请咨询律师或学校法务。文档先写决定,促成这个决定的对比分析留在下面作为背景。这个 PR 没有添加 LICENSE 文件(见决定的第一点),所以仓库默认仍是"保留所有权利"。资料读取于 2026-11-01;查不到的地方写作"未核实"。

This is not legal advice. It collects public sources and gives general suggestions. For decisions about publishing, commercial licensing, or anything that touches the teacher's work, talk to a lawyer or the university's legal office. The decision is written down first, and the comparison that led to it stays below as background. This pull request adds no LICENSE file (see the first point of the decision), so the repository is still "all rights reserved" by default. Sources were read on 2026-11-01. Where something could not be checked it says "not verified".

## 决定 / Decision

1. 许可证文件放在另一个 PR 里添加(分支 `feature/license`,PR 5),不在这个 PR 中。在那个 PR 合并之前,仓库仍然是"保留所有权利"。

   The license files are added in a separate pull request (branch `feature/license`, PR 5), not in this one. Until that one is merged the repository stays "all rights reserved".

2. 代码(`index.html`、`pipeline/`、`tools/`、`remote/`,以及 `engine-config/` 里我们自己写的部分)采用 PolyForm Noncommercial License 1.0.0。它允许任何非商业目的的使用、修改和分发(个人学习、研究、业余爱好项目、学校和大学等),条件是许可条款和 `Required Notice:` 行随副本一起传递。商业使用不在许可范围内([原文](https://github.com/polyformproject/polyform-licenses/blob/1.0.0/PolyForm-Noncommercial-1.0.0.md))。

   Code (`index.html`, `pipeline/`, `tools/`, `remote/` and the parts of `engine-config/` that we wrote) is under the PolyForm Noncommercial License 1.0.0. It allows use, modification and distribution for any noncommercial purpose (personal study, research, hobby projects, schools and universities, and similar), on the condition that the license terms and the `Required Notice:` line travel with every copy. Commercial use is outside the license ([source text](https://github.com/polyformproject/polyform-licenses/blob/1.0.0/PolyForm-Noncommercial-1.0.0.md)).

3. 我们自己的数据和文档(SGF 变化树结构、评估数值、README 和 `docs/`,不含老师的讲解)采用 CC BY-NC-SA 4.0。任何人都可以在署名的前提下复制、分享和改编,但只限非商业目的,改编后的版本必须使用相同的许可([许可证概要](https://creativecommons.org/licenses/by-nc-sa/4.0/))。

   Our own data and docs (the SGF variation structure, the evaluation numbers, the README and `docs/`, without the teacher's commentary) are under CC BY-NC-SA 4.0. Anyone may copy, share and adapt them with credit, for noncommercial purposes only, and adapted versions must carry the same license ([license summary](https://creativecommons.org/licenses/by-nc-sa/4.0/)).

4. 老师的讲解文字不在上述任何许可证的范围内,署名归原作者陈林涛,正在迁移到私有仓库。公开仓库保留变化树、评估数据,以及带时间点的视频链接。

   The teacher's commentary is excluded from every license above, its credit goes to the original author 陈林涛, and it is being moved to a private repository. The public repository keeps the variation trees, the evaluations and the video links with time stamps.

5. 外部贡献通过 DCO 签署(每个提交带一行 `Signed-off-by`)接收,再加一句话:维护者可以把贡献连同项目一起重新授权。最终措辞见 `CONTRIBUTING.md`。

   Outside contributions come in under a DCO sign off (a `Signed-off-by` line on each commit), plus a sentence saying the maintainer may relicense contributions together with the project. The final wording is in `CONTRIBUTING.md`.

6. 为什么这样决定:作者希望别人可以免费改编和再创作(非商业使用、修改和非商业再分发),但必须署名。这两份许可把署名变成法律条件,README、查看器页脚和 SGF 根节点里的 `AP`、`CP`、`SO` 属性则让正确署名既容易做到又容易被看到。署名的具体写法在 `NOTICE.md` 里。

   Why this decision: the author wants others to be able to remix the work for free, with noncommercial use, modification and noncommercial redistribution, but they have to credit it. The two licenses make credit a legal condition, and the README, the viewer footer and the `AP`, `CP` and `SO` properties in the SGF root node make correct credit easy to give and easy to see. The exact wording of the credit is in `NOTICE.md`.

7. 考虑过但没有采用的更严方案:PolyForm Strict License 1.0.0(只允许非商业使用,不允许分发,也不允许修改),以及 CC BY-NC-ND 4.0(只允许署名后原样分享,不允许分发改编后的版本)。这份文档的上一版和第一版许可证 PR 曾选用它们,现在不再采用,因为它们同时挡住了作者希望鼓励的改编和再创作。

   The stricter options that were considered and not chosen are the PolyForm Strict License 1.0.0 (noncommercial use only, no distribution and no changes) and CC BY-NC-ND 4.0 (unchanged sharing with credit only, no distribution of adapted versions). The previous version of this document and the first license pull request used them. They are dropped now because they also block the remixing that the author wants to encourage.

有几点需要请人把关:(1) 许可证授予的修改和再分发自由,对已经被别人拿走的副本是不可撤销的;以后可以对新版本改用更严的条款,但管不到旧副本(见第 2 节)。(2) "非商业"有灰色地带,在德国尤其如此(见 3.7 和第 6 节)。(3) 署名只有在作品被分发或发布时才是法律要求,私下使用不需要署名。(4) PolyForm Noncommercial 本身允许修改,所以贡献者准备 PR 不再需要额外的许可;无论许可证怎么写,GitHub 上的 fork 也仍然可以进行,因为 GitHub 的条款授予了这项权利。

A few points to have checked: (1) The freedom to modify and redistribute that the licenses grant is irrevocable for copies people have already taken. Stricter terms can be used for new versions later, but they do not reach old copies (see section 2). (2) "Noncommercial" has grey areas, in Germany especially (see 3.7 and section 6). (3) Credit is only legally required when the work is distributed or published, private use needs no credit. (4) PolyForm Noncommercial allows changes by itself, so a contributor needs no extra permission to prepare a pull request, and forking on GitHub stays possible whatever the license says, because the GitHub terms grant it.

## 0. 简短结论(写于决定之前,见上文) / Short answer (written before the decision, see above)

1. 许可证以后可以改。版权人只有你一人时,新版本可以采用任何条款;已经发出去的副本仍按当时附带的条款。现在没有 LICENSE 文件,没有任何人拿到过授权,所以此刻是最容易做选择的时候。

   The license can be changed later. A sole copyright holder can pick any terms for new versions, and copies already handed out stay under the terms they came with. There is no LICENSE file today, so nobody holds a grant yet, which makes this the easiest moment to choose.

2. 想表达"别人不能靠它盈利,我自己保留盈利的权利",最贴切的是:代码源码可见,采用非商业许可证,再加上按需另行提供的商业许可。这类许可证都不是 OSI 意义上的开源,应当称为"源码可见"(source available)。

   To say "others may not profit from this, I keep the right to profit" the closest fit is source available code under a non-commercial license, plus a separate commercial license on request. None of these licenses are open source in the OSI sense, and they should be called "source available".

3. 推荐方案:代码用 PolyForm Noncommercial 1.0.0;我们自己的 SGF 结构、评估数值和文档用 CC BY-NC-SA 4.0;外部贡献用 DCO 加一条允许重新授权的条款(草案在 CONTRIBUTING.md 里)。

   Recommended: PolyForm Noncommercial 1.0.0 for the code, CC BY-NC-SA 4.0 for our own SGF structure, evaluation numbers and docs, and DCO plus a relicensing grant for outside contributions (a draft is in CONTRIBUTING.md).

4. 老师的讲解文字不属于我们,我们也无权授权。它必须排除在上面所有许可证之外。公开仓库里现在有大段转写,所以应尽快写一份明确的声明;中期再把转写文字移出公开仓库,只保留视频链接和时间点。

   The teacher's commentary text is not ours and we cannot license it. It has to stay outside every license above. The public repository currently holds long transcripts, so write a clear notice soon and, in the medium term, move the transcript text out of the public repo and keep only video links with time stamps.

5. 第三方软件(KataGo、yt-dlp、faster-whisper 等)我们只是调用,并不随仓库分发,所以它们的分发义务基本没有触发。一旦把二进制、权重文件或代码拷贝放进仓库、发布包或镜像,义务就开始了。

   Third party software (KataGo, yt-dlp, faster-whisper and so on) is only called, not shipped, so its distribution duties are mostly not triggered. They start the moment a binary, weight file or code copy goes into the repository, a release or an image.

## 1. 仓库里有什么,权利在谁手里 / What is in the repository and who holds the rights

| 内容 / Content | 位置 / Where | 权利人(我的判断) / Rights holder (best reading) | 备注 / Note |
|---|---|---|---|
| 查看器、流水线、工具、远程批处理脚本 / Viewer, pipeline, tools, remote batch scripts | `index.html`, `pipeline/`, `tools/`, `remote/` | 作者本人 / The author | 可以授权 / Can be licensed |
| 变化树结构、KataGo 的评估数值、要点的编排方式 / Variation tree structure, KataGo evaluation numbers, how the key points are arranged | `data/sgf/`,以及 `data/library.js` 中非转写的部分 / `data/sgf/`, non-transcript parts of `data/library.js` | 作者(引擎输出加上作者的编排) / The author (engine output plus the author's arrangement) | 可以授权。单纯的一串棋步是否受保护,各国不同,未核实 / Can be licensed. Whether a bare sequence of Go moves is protected at all depends on the country, not verified |
| 老师的讲解(节点里讲解标记后面的文字) / Teacher commentary (text after the commentary markers in the nodes) | 四个已填充的 SGF(约 450 KB)和 `data/library.js` / The four filled SGF files (about 450 KB) and `data/library.js` | 讲解者陈林涛 / Chen Lintao (陈林涛), the speaker | 我们无权授权。转写和整理不会让版权转移 / Cannot be licensed by us. Transcribing and tidying does not move the copyright |
| 从口述中提炼的要点 / Key points distilled from the spoken text | `pipeline/kp_*.json` 及对应节点 / `pipeline/kp_*.json` and the matching nodes | 源自老师的讲解,按衍生内容对待 / Derived from the teacher's explanation, treat as derivative | 同样要谨慎处理 / Handle with the same care |
| 视频清单(标题、BV 号) / Video list (titles, BV ids) | `data/sources/*/index.json` | 标题是视频作者写的短文本,BV 号和链接属于事实信息 / Titles are short texts by the video authors, ids and links are facts | 风险低,但不是零 / Low risk, not zero risk |
| 错别字词典 / Typo dictionary | `pipeline/fixdict.json` | 作者本人 / The author | 可以授权 / Can be licensed |

## 2. 许可证以后还能改吗 / Can the license change later

能改。实际规则如下:

Yes. The rules in practice:

- 没有 LICENSE 文件,就是保留所有权利。别人只拥有 GitHub 服务条款给的权利,也就是在 GitHub 内查看和 fork 公开仓库;他们无权使用、修改或再分发代码([choosealicense](https://choosealicense.com/no-permission/)、[GitHub 条款 D.5](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service))。现在添加许可证只是增加授权,没有人因此失去什么。

  No LICENSE file means all rights reserved. Other people only have what the GitHub terms of service give them, which is viewing and forking a public repository inside GitHub. They have no right to use, change or redistribute the code ([choosealicense](https://choosealicense.com/no-permission/), [GitHub terms D.5](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)). Adding a license now only adds permissions, so nobody loses anything.

- 只要你是唯一的版权人,未来版本的许可证由你决定:可以更严,可以更松,也可以双重授权。

  While you are the only copyright holder you decide the license of future versions: stricter, looser, or dual.

- 已经发出的版本和副本仍然按当时附带的条款。Creative Commons 明确说,它的许可证除了对违约者之外不可撤销:许可人可以停止分发,但已经拿到副本的人可以继续按原条款使用([CC FAQ](https://creativecommons.org/faq/))。公司改许可证通常也只对新版本生效,HashiCorp 把 Terraform 改成 Business Source License 就是常被提到的例子。这个例子我只读到了搜索摘要,其 FAQ 页面本身没有显示答案原文,所以具体说法未核实。

  Versions and copies that were already handed out stay under the terms they came with. Creative Commons says plainly that its licenses cannot be revoked except against someone who breaks them. The licensor may stop distributing, but people who already have a copy may keep using it under the original terms ([CC FAQ](https://creativecommons.org/faq/)). Companies that change license usually apply the new terms to new releases only. HashiCorp's move of Terraform to the Business Source License is the well known example. Only a search summary was read for that one and the FAQ page itself did not show the answer text, so the wording is not verified.

- 所以放宽永远可以,收紧只对未来版本有效。这正是建议先选偏严选项的理由:以后想改成 MIT,只需要你自己同意;而以后再收紧,管不到已经拿到旧版本的人。

  So loosening is always possible and tightening only works for future versions. That is a good reason to start with the stricter option: moving to MIT later needs only your own consent, while tightening later cannot reach people who already have an older copy.

- 外部贡献者是个关键点。每位贡献者对自己贡献的部分拥有版权。GitHub 条款规定:向带许可证的仓库提交内容,默认按同一份许可证授权,除非另有协议([GitHub 条款 D.6](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service))。这意味着,如果仓库采用 PolyForm Noncommercial,贡献者默认也只授予这一种许可,你就不能单方面把他们写的代码交给商业客户,也不能单方面把整个项目换成别的许可证。CLA 通常包含项目方重新授权的权利;DCO 只是"我有权提交这份工作"的签名确认,并不给这项权利([opensource.com](https://opensource.com/article/18/3/cla-vs-dco-whats-difference)、[Kemitchell](https://writing.kemitchell.com/2021/07/02/DCO-Not-CLA))。要在合并第一个外部 PR 之前把机制定下来,CONTRIBUTING.md 里的贡献条款草案就是干这个的。目前只有一位提交者,所以这个问题暂时不存在。

  Outside contributors are the catch. Every contributor owns the copyright on what they contribute. GitHub's terms say that contributions to a repository with a license are licensed under that same license, unless a separate agreement says otherwise ([GitHub terms D.6](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)). If the repository uses PolyForm Noncommercial, contributors by default grant only that, and you could not hand their code to a commercial customer or switch the whole project to another license on your own. A CLA usually includes the right for the project to relicense. A DCO is only a sign-off that you may submit the work and does not give that right ([opensource.com](https://opensource.com/article/18/3/cla-vs-dco-whats-difference), [Kemitchell](https://writing.kemitchell.com/2021/07/02/DCO-Not-CLA)). Settle the mechanism before the first outside pull request is merged. The draft contribution terms in CONTRIBUTING.md do this. At the moment there is only one committer, so the problem does not exist yet.

- 你的许可证只管你自己写的部分。你所依赖的库和工具仍然适用它们各自的许可证(见第 5 节)。

  Your license only covers what you wrote. Libraries and tools you depend on keep their own licenses (section 5).

- 如果其中有部分是在 TUM 的课程、实习或学生科研工作中写的,先弄清楚归属。纯属个人爱好的项目通常没有这个问题。

  If any part was written as part of a TUM course, internship or student research job, check who owns it first. A purely private hobby project normally has no such issue.

## 3. "别人不能盈利,我保留盈利权"的几种方案 / Options for "others may not profit, I keep the right to"

| 方案 / Option | 是否满足目标 / Meets the goal | 适合 / Best for | 是否 OSI 开源 / OSI open source | 主要风险 / Main risk |
|---|---|---|---|---|
| PolyForm Noncommercial 1.0.0 | 满足:允许使用、修改和分发,但仅限非商业目的 / Yes: use, modify and distribute are allowed, for non-commercial purposes only | 软件 / Software | 否 / No | "非商业"仍有灰色地带,在 GitHub 上也不常见 / "Non-commercial" still has grey areas, and it is not a common sight on GitHub |
| CC BY-NC-SA 4.0(或 BY-NC 4.0) / CC BY-NC-SA 4.0 (or BY-NC 4.0) | 满足:署名、非商业、衍生作品沿用同样条款 / Yes: attribution, non-commercial, derivatives under the same terms | 数据、文字、图片 / Data, text, images | 否(也不是软件许可证) / No (and not a software license) | Creative Commons 自己不建议用于软件,而且"NC"的含义有争议 / Creative Commons itself advises against it for software, and the meaning of NC is disputed |
| Business Source License 1.1 | 部分满足:生产使用需要商业许可,但到期后自动转成开源 / Partly: production use needs a commercial license, but it turns into open source on a set date | 服务器软件的商业保护 / Commercial protection for server software | 否 / No | 最多四年后别人就能合法商用,与目标相反 / After at most four years others may use it commercially, which is the opposite of the goal |
| 自拟"源码可见,商用请联系我"(双重授权) / Custom "source visible, ask for a commercial license" (dual licensing) | 取决于条款写得怎样 / Depends on the wording | 想完全自己掌控 / Complete control | 否 / No | 自己写条款容易留漏洞,没有律师不建议 / Writing your own terms invites loopholes, so avoid it without a lawyer |

### 3.1 PolyForm Noncommercial 1.0.0

它授予为非商业目的使用、修改和分发软件的权利。条文明确列出了允许的情形:为增进公共知识而做的研究、实验和测试,个人学习,私人娱乐,业余爱好项目,以及慈善组织、学校和大学、公共研究机构、公共安全与卫生机构、环保组织和政府机构的使用,不论其资金来源([SPDX 页面](https://spdx.org/licenses/PolyForm-Noncommercial-1.0.0.html)、[原文](https://github.com/polyformproject/polyform-licenses/blob/1.0.0/PolyForm-Noncommercial-1.0.0.md))。它含有专利许可;要求转交副本的人附上条款(或其网址)以及你提供的 `Required Notice:` 行;被书面告知违约的被许可人,在 32 天内改正即可恢复授权;不允许再许可或转让。它是专为软件起草的,有 SPDX 标识 `PolyForm-Noncommercial-1.0.0`。商业用户需要另外来找你签协议,这就是双重授权的部分。

It grants the right to use, change and distribute the software for non-commercial purposes. The text lists permitted cases: research, experiments and testing for public knowledge, personal study, private entertainment, hobby projects, and use by charities, schools and universities, public research bodies, safety and health organizations, environmental groups and government institutions, however they are funded ([SPDX page](https://spdx.org/licenses/PolyForm-Noncommercial-1.0.0.html), [source text](https://github.com/polyformproject/polyform-licenses/blob/1.0.0/PolyForm-Noncommercial-1.0.0.md)). It includes a patent license, requires anyone passing it on to include the terms (or their URL) and any `Required Notice:` lines you provide, lets a licensee who is told in writing about a violation recover by fixing it within 32 days, and does not allow sublicensing or transfer. It was drafted for software and has an SPDX identifier, `PolyForm-Noncommercial-1.0.0`. Commercial users have to come to you for a separate agreement, which is the dual licensing part.

### 3.2 CC BY-NC-SA 4.0 或 BY-NC 4.0 / CC BY-NC-SA 4.0 or BY-NC 4.0

Creative Commons 不建议把自己的许可证用于软件,因为它们缺少源代码和专利方面的条款,也和主流软件许可证不兼容。它们适合文档、图片和数据([CC FAQ](https://creativecommons.org/faq/))。4.0 版本还把欧盟的数据库权按同样条件一并授权。你可以另外向别人提供商业许可,不过单独的协议只约束签署协议的双方。SA(相同方式共享)会迫使衍生的数据集继续使用 BY-NC-SA,有利于你的目标;单纯的 BY-NC 没有这一点。

Creative Commons advises against using its licenses for software, because they lack source code and patent terms and clash with the major software licenses. They suit documents, images and data ([CC FAQ](https://creativecommons.org/faq/)). Version 4.0 also licenses the EU database right on the same terms. You may offer a commercial license to others on the side, although a separate agreement binds only the parties who sign it. The SA part forces derivative datasets to stay BY-NC-SA, which supports your goal, while plain BY-NC does not.

"非商业"的灰色地带是真实存在的:

The grey area of "non-commercial" is real:

- 德国:科隆地方法院(2014)认为,公共广播电台的网站使用 CC BY-NC 图片属于商业使用。科隆高等法院(2014 年 10 月 31 日,6 U 60/14)把 CC 许可证当作格式条款,没能判断该使用是否属于商业使用,并适用了 BGB 第 305c 条第 2 款:含义不清时作不利于条款起草方的解释,这里的起草方就是许可人。因此在这一点上电台没有违约,不过它在其他方面败诉,比如擅自修改图片、删掉署名([lhr-law 摘要](https://www.lhr-law.de/en/magazine-en/cologne-higher-regional-court-confirms-use-of-photographs-by-deutschlandradio-in-breach-of-cc-licence-but-not-for-commercial-use/)、[netzpolitik.org](https://netzpolitik.org/2014/der-dritte-streich-olg-koeln-zu-deutschlandradios-nutzung-cc-lizenzierter-fotos-mit-nc-modul/))。你在德国,"NC"含糊的地方可能被作不利于你的解读。

  Germany: the Landgericht Köln (2014) held that a public broadcaster's website using a CC BY-NC picture was a commercial use. The Oberlandesgericht Köln (31 October 2014, 6 U 60/14) treated the CC license as standard terms, could not decide whether the use was commercial, and applied section 305c(2) of the BGB, which resolves doubt against the party who wrote the terms, here the licensor. On that point the broadcaster was therefore not in breach, although it lost on other points such as editing the picture and removing the name ([lhr-law summary](https://www.lhr-law.de/en/magazine-en/cologne-higher-regional-court-confirms-use-of-photographs-by-deutschlandradio-in-breach-of-cc-licence-but-not-for-commercial-use/), [netzpolitik.org](https://netzpolitik.org/2014/der-dritte-streich-olg-koeln-zu-deutschlandradios-nutzung-cc-lizenzierter-fotos-mit-nc-modul/)). You live in Germany, so unclear NC wording may be read against you.

- 美国:在 Great Minds 诉 FedEx Office 案(第二巡回法院,2018)中,复印店替学区复印教材没有违反 NC 条款,因为行使权利的是获得许可的学区([CC 法律数据库](https://legaldb.creativecommons.org/en/cases/15/))。

  United States: in Great Minds v. FedEx Office (Second Circuit, 2018) a copy shop copying course materials for school districts did not breach the NC term, because the licensed school districts were the ones exercising the rights ([CC legal database](https://legaldb.creativecommons.org/en/cases/15/)).

### 3.3 Business Source License 1.1

源码公开,非生产使用免费,生产使用需要商业许可,除非"附加使用授权"允许。到了转换日期(最晚为首次公开发布后四年),许可证会自动转成与 GPL v2 或更高版本兼容的开源许可证。MariaDB 自己的 FAQ 也说 BSL 不是开源许可证([MariaDB BSL FAQ](https://mariadb.com/bsl-faq-adopting/))。转换之后别人可以合法商用,与你的目标冲突;而且它本来是为保护服务器软件不被商业对手抢走而设计的,对一份离线学习资料来说,"生产使用"没有明确含义。不推荐。

Source is public, non-production use is free and production use needs a commercial license unless the additional use grant allows it. The license converts automatically to an open source license compatible with GPL v2 or later on a change date that is at most four years after the first public release. MariaDB's own FAQ says the BSL is not an open source license ([MariaDB BSL FAQ](https://mariadb.com/bsl-faq-adopting/)). Others may use the code commercially after the conversion, which conflicts with your goal, and it was designed to protect server software against commercial competitors, so "production use" has no clear meaning for an offline study resource. Not recommended.

### 3.4 自拟条款与双重授权 / Custom terms and dual licensing

最稳妥的做法是:用一份现成的非商业许可证公开(3.1 或 3.2),有人需要时再另签商业合同。在 README 里写一句"商业使用请联系作者"就够了,不要自己改写条款。联系方式由你决定;不想公开邮箱的话,用 GitHub issue 或私信也行。

The safest way is to publish under an existing non-commercial license (3.1 or 3.2) and sign a separate commercial contract when someone asks. Put one sentence in the README, such as "for commercial use please get in touch". Do not rewrite the terms yourself. How people reach you is up to you. A GitHub issue or a message works if you do not want to publish an email address.

### 3.5 它们算开源吗,会有什么后果 / Are they open source, and what follows

它们都不算。开源定义(OSD)禁止歧视个人或团体(第 5 条),也禁止限制使用领域,并明确包括商业使用(第 6 条)([OSD](https://opensource.org/osd))。由此带来的后果:

None of them is. The Open Source Definition forbids discrimination against persons or groups (point 5) and against fields of endeavor, which explicitly includes commercial use (point 6) ([OSD](https://opensource.org/osd)). Consequences:

- 不要称它为"开源",要说"源码可见"(source available)。

  Do not call it "open source". Say source available.

- 有些公司、Linux 发行版和基金会不接受这类代码,外部贡献者也可能更少。

  Some companies, Linux distributions and foundations will not accept such code, and outside contributors may be fewer.

- 别人不能把你的代码并入 MIT 或 GPL 项目再发布。

  Others cannot merge your code into an MIT or GPL project and republish it.

- GitHub 如何显示 PolyForm 许可证(是否能识别),未核实。

  How GitHub displays a PolyForm license (whether it detects it) is not verified.

### 3.6 GitHub 的 fork 与展示 / GitHub forks and display

GitHub 条款规定,仓库设为公开就等于允许别人在 GitHub 上查看和 fork。这项权利不取决于你选的许可证,所以许可证无法禁止别人在 GitHub 上 fork 一个公开仓库([条款 D.5](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service))。许可证管的是别人 fork 之后可以怎么用。想禁止 fork,只能把仓库设为私有。

The GitHub terms say that making a repository public allows others to view it and to fork it on GitHub. That right does not depend on your license, so a license cannot forbid forking a public repository on GitHub ([terms D.5](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service)). A license governs what people may do with a fork afterwards. To prevent forking, make the repository private.

### 3.7 "非商业"含糊的风险与维权成本 / Vague "non-commercial" and the cost of enforcing it

灰色情形包括:带广告的个人博客、公司内部员工使用、收费的培训班、有赞助的社区。PolyForm 对允许的使用者和用途列得比 CC 更细,歧义更少,但边界仍需要解释。上面的德国案例说明含糊的措辞会怎样被解读。一个人的维护者很难发现并追究滥用,所以许可证的作用主要是一份清楚的声明,以及发生纠纷时有据可依;它在技术上拦不住任何人。

Grey cases include a personal blog with ads, internal use by a company's staff, a paid training course, and a sponsored community. PolyForm lists permitted users and uses in more detail than CC and is less ambiguous, but the border still needs interpretation. The German case above shows how unclear wording can be read. A single maintainer will find it hard to notice and pursue misuse, so a license mostly works as a clear statement and something to point to in a dispute. It does not stop anyone technically.

## 4. 推荐方案 / Recommendation

这是做出决定之前的推荐,文首的决定与它一致:代码用 PolyForm Noncommercial,数据和文档用 CC BY-NC-SA。文首的决定曾一度改为更严的 PolyForm Strict 和 CC BY-NC-ND,后来又改了回来(理由见决定的第 6、7 点)。本节其余内容,包括关于老师讲解文字的建议,仍然适用。

This was the recommendation before the decision, and the decision at the top matches it: PolyForm Noncommercial for the code, CC BY-NC-SA for data and docs. The decision was briefly changed to the stricter PolyForm Strict and CC BY-NC-ND and then changed back (see points 6 and 7 of the decision for the reasons). The rest of this section, including the advice on the teacher's commentary, still applies.

| 内容 / Content | 许可证 / License | 理由 / Reason |
|---|---|---|
| 代码:`index.html`、`pipeline/`、`tools/`、`remote/`,以及 `engine-config/` 里我们自己写的部分 / Code: `index.html`, `pipeline/`, `tools/`, `remote/`, the parts of `engine-config/` that we wrote | PolyForm Noncommercial 1.0.0,附一行 `Required Notice: Copyright (c) 2026 Xtraordinaire9911`(用 GitHub 用户名,不用真名或邮箱) / PolyForm Noncommercial 1.0.0 with a line `Required Notice: Copyright (c) 2026 Xtraordinaire9911` (use the GitHub name, not a real name or email) | 专为软件起草,明确允许个人学习、研究和教育,围棋爱好者可以放心用,商业用户则必须来找你 / Written for software, names personal study, research and education as allowed, so Go hobbyists are covered, and commercial users have to ask you |
| 我们的 SGF 变化树结构、评估数值、自己写的文档(`README`、`docs/`) / Our SGF variation structure, evaluation numbers, own docs (`README`, `docs/`) | CC BY-NC-SA 4.0,范围限定为"本项目的原创部分",并明确排除老师的讲解 / CC BY-NC-SA 4.0, limited to "the original parts of this project" and explicitly excluding the teacher's commentary | 数据和文字的通行做法,SA 让衍生数据集保持非商业,4.0 还覆盖数据库权 / Standard for data and text, SA keeps derivative datasets non-commercial, 4.0 covers database rights |
| 老师的讲解,以及据此提炼的要点 / The teacher's commentary and key points taken from it | 不授权。声明权利属于陈林涛,本项目的任何许可证都不覆盖它 / Not licensed. State that the rights belong to Chen Lintao and that no license of this project covers it | 我们不是权利人,没有权利授予任何东西 / We are not the rights holder and cannot grant anything |
| 视频清单(标题、BV 号、链接) / Video list (titles, BV ids, links) | 保留,并注明出处 / Keep, with the source named | 事实信息和链接,风险低 / Facts and links, low risk |
| 外部贡献 / Outside contributions | DCO 加一条重新授权条款(草案在 CONTRIBUTING.md 里) / DCO plus a relicensing grant (draft in CONTRIBUTING.md) | 保留商业授权和以后更换许可证的可能 / Keeps the option of commercial licensing and of changing the license later |

如果觉得全仓库(去掉老师的文字)用同一份许可证更省事,整个仓库用 PolyForm Noncommercial 也行,但对数据和文档不够贴切,而且"软件"的定义是否涵盖纯数据文件,未核实。上面这种拆开的方案更合适。

If one license for everything (minus the teacher's text) is easier, PolyForm Noncommercial for the whole repository works, but it is worse for data and docs, and whether "software" covers plain data files is not verified. The split above is the better fit.

按这个决定新增的文件(它们放在 PR 5 里,不在这个分支上):

Files that follow from the decision (they are in PR 5, not on this branch):

- `LICENSE`:PolyForm Noncommercial 1.0.0 全文,加上 `Required Notice:` 一行。

  `LICENSE` with the full PolyForm Noncommercial 1.0.0 text and the `Required Notice:` line.

- `LICENSE-DATA.txt`:CC BY-NC-SA 4.0 官方法律文本,对老师文字的排除写在 `NOTICE.md` 里。

  `LICENSE-DATA.txt` with the official CC BY-NC-SA 4.0 legal code. The exclusion for the teacher's text is written in `NOTICE.md`.

- `NOTICE.md`:各部分适用的许可、署名写法、老师内容的声明、商业使用的联系方式和贡献条款。

  `NOTICE.md` with the scope of each license, how to credit the project, the notice about the teacher's content, how to ask for commercial use and the contribution terms.

- 可选:在源码文件开头加 `SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0`。

  Optionally `SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0` at the top of source files.

- README 里的许可证段落,例如:"代码:PolyForm Noncommercial 1.0.0。数据与文档(不含老师的讲解):CC BY-NC-SA 4.0。讲解内容来自陈林涛的公开视频,版权属于原作者,不在上述许可证覆盖范围内。商业使用请联系作者。本项目是源码可见,不是开源软件。"

  A README license paragraph, for example: "Code: PolyForm Noncommercial 1.0.0. Data and docs, except the teacher's commentary: CC BY-NC-SA 4.0. The commentary comes from public videos by Chen Lintao, the copyright belongs to the author, and it is not covered by these licenses. For commercial use please get in touch. This project is source available, not open source."

### 4.1 老师的讲解文字怎么处理 / What to do about the teacher's commentary

讲解文字是他在视频里所说内容的转写。转写和整理属于对他人作品的复制和改编,版权仍归他所有。仓库里的转写几乎是逐字稿,远远超出了简短引用的范围。

The commentary is a transcript of what he says in the videos. Transcribing and tidying is copying and adapting someone else's work, and the copyright stays with him. The transcripts in the repo are close to word for word and go far beyond a short quotation.

法律上的要点(一般性说明,请核对官方原文并咨询律师):

The legal points, in general terms (check the official texts and ask a lawyer):

- 中国:口述作品是受保护的作品类型(《著作权法》第三条)。两种常见的合理使用情形是:为个人学习、研究或欣赏而使用已发表的作品,以及为介绍、评论某一作品或说明某一问题而适当引用。两者都要求指明作者姓名和作品名称,不得影响作品的正常使用,也不得不合理地损害权利人的合法权益(第二十四条)。通过信息网络向公众提供作品是另一项专有权利(第十条)。把整份转写发布到 GitHub 上,不属于个人学习([全国人大网](http://www.npc.gov.cn/npc/c30834/202011/848e73f58d4e4c5b82f69d25d46048c6.shtml),并对照了[国家版权局的版本](https://www.ncac.gov.cn/xxfb/flfg/flfg_532/202103/t20210309_50530.html))。

  China: oral works are a protected category (Copyright Law, Article 3). The two common fair use cases are using a published work for personal study, research or appreciation, and quoting appropriately to introduce or comment on a work. Both need the author's name and the title of the work to be given, must not interfere with normal use, and must not unreasonably harm the owner's rights (Article 24). Making a work available to the public over an information network is a separate exclusive right (Article 10). Publishing a full transcript on GitHub is not personal study ([National People's Congress](http://www.npc.gov.cn/npc/c30834/202011/848e73f58d4e4c5b82f69d25d46048c6.shtml), checked against the [copyright administration's copy](https://www.ncac.gov.cn/xxfb/flfg/flfg_532/202103/t20210309_50530.html)).

- 德国:为私人使用而制作的复制品,既不得散布,也不得用于公开再现(《著作权法》第 53 条第 6 款)。科研目的的文本与数据挖掘(第 60d 条)只允许向明确限定的人群提供,用于共同研究或核查质量,之后必须终止公开访问。一般性的文本与数据挖掘(第 44b 条)要求复制品在不再需要时删除,权利人还可以保留自己的权利。引用权(第 51 条)以引用目的所需的范围为限([第 53 条](https://www.gesetze-im-internet.de/urhg/__53.html)、[第 60d 条](https://www.gesetze-im-internet.de/urhg/__60d.html)、[第 51 条](https://www.gesetze-im-internet.de/urhg/__51.html)、[44b 条的评述](https://cms.law/de/deu/legal-updates/text-und-data-mining-nach-dem-neuen-urheberrecht))。这些规定都不允许公开发布整份转写。

  Germany: copies made for private use may neither be distributed nor used for public reproduction (section 53(6) UrhG). The research text and data mining rule (section 60d) only lets you share with a clearly limited group for joint research or for checking quality, and public access must end afterwards. The general text and data mining rule (section 44b) requires copies to be deleted once no longer needed, and right holders can reserve their rights. The right to quote (section 51) is limited to what the purpose of quoting justifies ([section 53](https://www.gesetze-im-internet.de/urhg/__53.html), [section 60d](https://www.gesetze-im-internet.de/urhg/__60d.html), [section 51](https://www.gesetze-im-internet.de/urhg/__51.html), [commentary on 44b](https://cms.law/de/deu/legal-updates/text-und-data-mining-nach-dem-neuen-urheberrecht)). None of these allow publishing a full transcript.

- README 里"作者要求即刻移除"这句话很有礼貌,但它不是授权,也不能代替许可证。

  The README sentence "we will remove it immediately if the author asks" is polite, but it is not permission and does not replace a license.

- B 站的用户协议对转写或下载有没有规定:未核实。

  Whether the Bilibili terms of use say anything about transcription or downloading: not verified.

建议,由轻到重,可以叠加:

Suggestions, from light to heavy, which can be combined:

1. 马上就能做,零成本:在 README 和 `NOTICE.md` 里写明老师的讲解不属于本项目,也不被任何许可证覆盖,并且不要把整个仓库说成"都在某一份许可证之下"。

   Right away and free: state in the README and in `NOTICE.md` that the teacher's commentary does not belong to this project and is not covered by any license, and never describe the whole repository as being under one license.

2. 中期,推荐拆分:公开仓库保留变化树、评估数据、带时间点的视频链接,以及你用自己的话写的要点;转写文字放进私有的数据仓库,或者只留在你自己的机器上,查看器把它当作可选的本地文件来加载(例如 `data/private/library.private.js`),这需要在单独的 feature 分支上改动 `pipeline/` 和 `index.html`。从转写里提炼出来的要点仍然源自转写,要么也放进私有部分,要么用自己的话重写并注明出处。

   Medium term, recommended: split. The public repo keeps the variation tree, the evaluations, video links with time stamps, and key points you wrote in your own words. The transcript text lives in a private data repository or only on your machine, and the viewer loads it as an optional local file (for example `data/private/library.private.js`), which needs changes in `pipeline/` and `index.html` on a separate feature branch. Key points distilled from the transcript are still derived from it, so either keep them private too or rewrite them in your own words with the source named.

3. 私信陈林涛(在 B 站),请求书面授权。写清你需要什么:转写能否公开、非商业的学习用途是否可以、怎样署名。这是最干净的办法,请保存好聊天记录。

   Ask Chen Lintao (a private message on Bilibili) for written permission. State what you need: whether the transcript may be public, whether non-commercial study use is fine, and how to credit him. This is the cleanest route. Keep the conversation.

4. 历史记录:已发布的 v0.1 提交、发布包,以及可能存在的 fork 和克隆里仍然带着这些文字,删除文件只影响新版本。想彻底清除,就得改写 git 历史并强制推送,会影响所有克隆。这是个大动作,目前没有做。如果作者提出异议,或者你要做拆分时,再考虑它。

   History: the published v0.1 commit, the release and any forks or clones still contain the text, and deleting files only affects new versions. Removing it completely means rewriting git history and force pushing, which affects every clone. That is a big step and has not been done. Consider it if the author objects or when you do the split.

5. 在自己的机器上用这些文字做个人学习,没有问题。

   Using the text on your own machine for your own study is fine.

## 5. 第三方软件与权重:分发时有什么要求 / Third party software and weights: what distribution requires

本仓库只是调用或导入下面这些工具,里面没有它们的代码、二进制或权重,所以它们的分发义务基本没有触发。义务从拷贝进入仓库、GitHub 发布包、Colab 或 Kaggle 数据集、或公开镜像的那一刻开始。

This repository only calls or imports the tools below. It contains none of their code, binaries or weights, so their distribution duties are mostly not triggered. They begin when a copy goes into the repo, a GitHub release, a Colab or Kaggle dataset or a public image.

| 组件 / Component | 许可证 / License | 在本项目里怎么用 / How it is used here | 分发时 / When shipping it | 来源 / Source |
|---|---|---|---|---|
| KataGo 程序 / KataGo program | MIT 风格。`cpp/external` 里的第三方部分(CLBlast、cutlass、nlohmann_json 等)各有自己的许可证 / MIT style. Third party parts in `cpp/external` (CLBlast, cutlass, nlohmann_json and others) have their own licenses | 以进程方式运行 `katago.exe` 或 Linux 版 / Runs `katago.exe` or the Linux build as a process | 保留版权和许可声明;分发二进制时还要带上内置第三方部分的许可证 / Keep the copyright and permission notice, and for binaries the licenses of the bundled third party parts | [KataGo LICENSE](https://github.com/lightvector/KataGo/blob/master/LICENSE) |
| KataGo 权重(本机文件 `kata1-tf3-b11c768-s12752M-d6531M.bin.gz`) / KataGo weights (local file `kata1-tf3-b11c768-s12752M-d6531M.bin.gz`) | "KataGo Neural Network License",宽松(可使用、复制、修改、分发、出售),需保留版权和许可声明。它覆盖官方 kata1 网络和标注为 KataGo 的额外网络;其他贡献者的额外网络可能没有明确条款;g170 网络是 CC0 / "KataGo Neural Network License", permissive (use, copy, modify, distribute, sell) with the copyright and permission notice kept. It covers the official kata1 networks and extra networks labelled KataGo. Extra networks from other contributors may have no stated terms. The g170 networks are CC0 | 在本机或云端从磁盘读取,不提交 / Read from disk locally or in the cloud, not committed | 附上声明。这个具体文件属于哪一类未核实,请到下载来源处确认 / Include the notice. Which group this exact file belongs to was not verified, please check where you downloaded it | [network license](https://katagotraining.org/network_license/), [network list](https://katagotraining.org/networks/) |
| KataGo 的分析输出(目差、胜率) / KataGo analysis output (scores, winrates) | 读到的 MIT 风格条款没有限制输出,但没有逐字对照全文 / The MIT style terms that were read do not restrict output, but the full text was not compared word by word | 写入 SGF 和 `a2.json` / Written into SGF and `a2.json` | 未发现要求 / None known | 同上 / same |
| yt-dlp | 源码是 Unlicense;用 PyInstaller 打包的发行版二进制含有 GPLv3+ 代码 / The source is under the Unlicense. Release binaries built with PyInstaller include GPLv3+ code | 用 `python -m yt_dlp` 下载视频 / `python -m yt_dlp` downloads the videos | 只在本机用就没有要求;分发它的二进制或含有它的镜像,就要履行 GPL 义务 / Nothing when only used locally. Shipping its binary or an image that contains it brings the GPL duties | [yt-dlp README](https://github.com/yt-dlp/yt-dlp) |
| faster-whisper | MIT | 语音转文字 / Speech to text | 保留声明 / Keep the notice | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) |
| Whisper 代码与权重 / Whisper code and weights | MIT(Whisper 仓库自述) / MIT, as stated by the Whisper repository | `small` 模型 / The `small` model | 保留声明。faster-whisper 转换版权重的许可证以其 Hugging Face 模型卡为准,未核实 / Keep the notice. The license of the converted faster-whisper weights follows their Hugging Face model card, not verified | [openai/whisper](https://github.com/openai/whisper) |
| CTranslate2(faster-whisper 的后端) / CTranslate2 (faster-whisper backend) | 未核实 / Not verified | 间接依赖 / Indirect dependency | | |
| numpy | BSD-3-Clause | `board.py`, `tr.py` | 保留声明 / Keep the notice | [numpy license](https://numpy.org/doc/stable/license.html) |
| ffmpeg | 取决于构建,是 LGPL 还是 GPL,用的是哪个未核实 / LGPL or GPL depending on the build, which one is used was not verified | 通过 `subprocess` 启动的外部程序 / External program started with `subprocess` | 不分发就没有要求 / Nothing unless you ship it | |
| OpenCV | README 提到用 OpenCV 识别棋盘,但在 `pipeline/` 里没有找到 `cv2` 的导入,README 可能已过时。许可证细节未核实 / The README mentions OpenCV for board recognition, but no import of `cv2` was found in `pipeline/`, so the README may be out of date. License details not verified | | | |
| 前端库、字体、CDN / Frontend libraries, fonts, CDNs | `index.html` 是单文件,引用检查只发现了 `data/library.js` / `index.html` is a single file. The reference check found only `data/library.js` | | 无 / None | 仓库自查 / repository check |

如果将来的发布包里带上了 KataGo 二进制、权重或打包版的 yt-dlp,要把对应的许可证文本放进 `NOTICE.md`;属于 GPL 的部分,还要说明源码从哪里获取。

If a release ever carries a KataGo binary, weights or a packaged yt-dlp, put the matching license texts in `NOTICE.md`, and for GPL parts say where the source can be obtained.

## 6. 关于中国与德国、欧盟的一段话 / One paragraph on China and Germany or the EU

中国著作权法保护口述作品,合理使用只限于个人学习研究,或者署名的适当引用。德国和欧盟的私人复制、文本与数据挖掘例外,同样不允许公开发布别人作品的整份转写。你在慕尼黑发布内容,你在当地的行为主要适用德国法,作品来源国(中国)的权利也可能有影响。具体适用哪国法律、是否构成侵权,要由律师或学校法务来判断,请不要只凭这份说明做决定。

Chinese copyright law protects oral works, and its fair use cases are limited to personal study or research and appropriate quotation with attribution. German and EU private copy and text and data mining exceptions do not allow publishing someone else's full transcript either. You publish from Munich, so German law mainly applies to what you do there, and rights in the country of origin (China) can matter as well. Which law applies and whether something infringes is a question for a lawyer or the university's legal office, so please do not rely on this note alone.

## 7. 下一步(都由你决定,这里一项也没做) / Next steps (all yours, none done here)

1. 已完成:本页开头的许可证决定。剩下的是合并添加 LICENSE 文件的那个 PR。

   Done: the license decision at the top of this page. What is left is merging the pull request that adds the LICENSE files.

2. 先把老师内容的声明加进 README 和 `NOTICE.md`(4.1 节第 1 条)。

   Add the teacher notice to the README and `NOTICE.md` first (section 4.1, point 1).

3. 把老师的讲解文字迁到私有仓库已经决定。要不要再向陈林涛请求授权,还没有定。

   The move of the teacher's commentary to a private repository is decided. Whether to also ask Chen Lintao for permission is still open.

4. `CONTRIBUTING.md` 里的贡献条款现在是最终措辞。合并外部 PR 之前,请律师看一遍,尤其是修改代码的许可部分。

   The contribution terms in `CONTRIBUTING.md` are now final wording. Have a lawyer read them before merging an outside pull request, especially the permission to modify the code.

5. 重要的决定请律师或学校法务过目。

   Have a lawyer or the university legal office read the important decisions.

6. 弄清 `kata1-tf3-b11c768-...` 的来源和它适用的许可证。

   Find out where `kata1-tf3-b11c768-...` came from and which license it carries.

7. 决定之后,按 `docs/WORKFLOW.md` 的流程,在单独的分支上添加 LICENSE 文件,并写进更新日志。

   When decided, add the LICENSE files on a branch of their own following `docs/WORKFLOW.md` and write it up in the changelog.

## 未核实项 / Not verified

- 各国如何看待单纯的一串棋步或一棵变化树。

  How different countries treat a bare sequence of Go moves or a variation tree.

- HashiCorp 许可证 FAQ 的原文(只读到了搜索摘要)。

  The original text of HashiCorp's license FAQ (only a search summary was read).

- GitHub 如何识别和显示 PolyForm。

  How GitHub detects and displays PolyForm.

- `kata1-tf3-b11c768-...` 属于哪一类 KataGo 网络、适用哪份许可证,以及 KataGo 许可证对输出的确切措辞。

  Which KataGo network family `kata1-tf3-b11c768-...` belongs to and which license applies, plus the exact wording of the KataGo license on outputs.

- CTranslate2、所用 ffmpeg 构建、OpenCV 以及 faster-whisper 转换版权重的许可证。

  Licenses of CTranslate2, the ffmpeg build in use, OpenCV and the converted faster-whisper weights.

- B 站用户协议对转写和下载的规定。

  What the Bilibili terms of use say about transcription and downloads.

- 中国法条:全国人大官网在所用工具里打不开(连接失败),所以条文序号以国家版权局网站上的版本为准。

  Chinese statute: the official site of the National People's Congress could not be opened from the tool used (the connection failed), so article numbers follow the copy on the copyright administration's site.

## 来源(2026-11-01 访问) / Sources (visited 2026-11-01)

- choosealicense, the default without a license / 无许可证时的默认状态: https://choosealicense.com/no-permission/
- GitHub terms of service (D.5 view and fork, D.6 contributions under the repository license) / GitHub 服务条款(D.5 查看与 fork,D.6 贡献按仓库许可证授权): https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
- PolyForm Noncommercial 1.0.0: https://spdx.org/licenses/PolyForm-Noncommercial-1.0.0.html and https://github.com/polyformproject/polyform-licenses/blob/1.0.0/PolyForm-Noncommercial-1.0.0.md
- Creative Commons FAQ (software, irrevocability, dual licensing, database rights) / CC 常见问题(软件、不可撤销、双重授权、数据库权): https://creativecommons.org/faq/
- Open Source Definition / 开源定义: https://opensource.org/osd
- BSL 1.1 FAQ: https://mariadb.com/bsl-faq-adopting/
- DCO and CLA / DCO 与 CLA: https://opensource.com/article/18/3/cla-vs-dco-whats-difference, https://writing.kemitchell.com/2021/07/02/DCO-Not-CLA, DCO text https://developercertificate.org/
- German NC case law / 德国关于 NC 条款的判例: https://www.lhr-law.de/en/magazine-en/cologne-higher-regional-court-confirms-use-of-photographs-by-deutschlandradio-in-breach-of-cc-licence-but-not-for-commercial-use/ and https://netzpolitik.org/2014/der-dritte-streich-olg-koeln-zu-deutschlandradios-nutzung-cc-lizenzierter-fotos-mit-nc-modul/
- Great Minds v. FedEx Office: https://legaldb.creativecommons.org/en/cases/15/
- Chinese Copyright Law (2020 amendment) / 中国《著作权法》(2020 年修正): http://www.npc.gov.cn/npc/c30834/202011/848e73f58d4e4c5b82f69d25d46048c6.shtml and https://www.ncac.gov.cn/xxfb/flfg/flfg_532/202103/t20210309_50530.html
- German UrhG sections 51, 53, 60d / 德国著作权法第 51、53、60d 条: https://www.gesetze-im-internet.de/urhg/__51.html, https://www.gesetze-im-internet.de/urhg/__53.html, https://www.gesetze-im-internet.de/urhg/__60d.html. Commentary on section 44b / 第 44b 条评述: https://cms.law/de/deu/legal-updates/text-und-data-mining-nach-dem-neuen-urheberrecht
- KataGo: https://github.com/lightvector/KataGo/blob/master/LICENSE and https://katagotraining.org/network_license/
- yt-dlp https://github.com/yt-dlp/yt-dlp, faster-whisper https://github.com/SYSTRAN/faster-whisper, Whisper https://github.com/openai/whisper, numpy https://numpy.org/doc/stable/license.html
