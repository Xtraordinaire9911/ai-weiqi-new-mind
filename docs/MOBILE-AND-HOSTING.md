# 手机版与托管准备 / Mobile edition and hosting preparation

本文记录手机和平板版查看器的设计,以及免费静态托管的调研结果和已经准备好但没有执行的配置。目前没有发布任何站点:没有开启 GitHub Pages,没有部署,没有注册账号,没有加 CI,也没有公开任何网址。

This document describes the design of the phone and tablet viewer, the research on free static hosting, and the configuration that is prepared but not executed. Nothing is published at the moment: no GitHub Pages, no deployment, no account, no CI and no public URL.

标记「未核实」的内容来自搜索结果摘要、第三方文章或我的记忆,没有在服务商官方页面上逐条确认。公开发布前请在官方页面核对价格、额度和条款。

Items marked "not verified" (未核实) come from search snippets, third party articles or memory and were not confirmed on the provider's official page. Check prices, limits and terms there before any publication.

## 手机版 / Mobile edition

### 布局 / Layout

页面按窗口尺寸分三种模式。竖屏且宽度不超过 1100 px(手机、平板竖屏、折叠屏展开)时,棋盘在最上方并保持粘性,评论和变化列表在下方滚动,底部固定一条控制栏。横屏且宽度不超过 1199 px(横屏手机、平板横屏)时,棋盘在左边、高度与窗口一致,右边是评论和变化列表。更宽的横屏窗口保持原来的三栏桌面布局,桌面行为没有改动。

The page has three modes by window size. In portrait up to 1100 px wide (phones, portrait tablets, unfolded foldables) the board sits on top and stays sticky, the commentary and the variation list scroll below it, and a control bar is fixed at the bottom. In landscape up to 1199 px wide (landscape phones and tablets) the board is on the left as tall as the window and the commentary and variations are on the right. Wider landscape windows keep the original three column desktop layout, so desktop behaviour is unchanged.

控制栏是 6 列 2 行的固定网格,每个按钮的位置固定,换手、缩放或换棋谱集合都不会让它移动。第一行:到开头、后退 5 手、上一手、下一手、前进 5 手、到结尾。第二行:缩小、放大、一个空档、变化(跳到变化列表)、AI 局部点、更多。手数、演示征子(讲解没提到征子时变灰,位置不变)、复制 SGF、训练、推演、目录、算力放在「更多」面板里。缩放只由你自己控制:换手时棋盘范围不会自动变;如果讲解提到的外围子在当前范围之外,棋盘下方的提示条会写出来,并带一个「显示全盘」按钮。目录(棋谱集合列表)和算力卡片放在一个抽屉里,选择一个集合后抽屉自动关闭。AI 推演卡片在评论下面,表格可以横向滑动。

The control bar is a fixed grid of 6 columns and 2 rows. Every button keeps its place, and stepping, zooming or switching the collection never moves one. Row one: jump to start, back 5 moves, previous, next, forward 5 moves, jump to end. Row two: zoom out, zoom in, a gap, variations (jumps to the variation list), AI dots, more. Move numbers, ladder demo (dimmed, not hidden, when the commentary does not mention a ladder), copy SGF, training, the engine button, the collection list and compute go into the "more" sheet. The zoom is controlled by you only: the visible part of the board never changes by itself when you step. If the commentary mentions outer stones that are outside the current view, the hint line under the board says so and offers a "显示全盘" (show the full board) button. The collection list and the compute card live in a drawer that closes after you pick a collection. The engine panel card sits below the commentary and its table scrolls sideways.

适配细节:用 `100dvh` 而不是 `100vh`;`viewport-fit=cover` 加 `env(safe-area-inset-*)` 避开刘海和 Home 指示条;输入框字体至少 16 px,避免 iOS 聚焦时自动放大;按钮、列表项、链接芯片最小 44 px;字号用 rem,跟随系统字体设置;页面没有横向滚动;深色和浅色两套配色都沿用原来的变量;`prefers-reduced-motion` 时关闭动画。

Details: `100dvh` instead of `100vh`; `viewport-fit=cover` with `env(safe-area-inset-*)` to stay clear of notches and the home indicator; inputs use at least 16 px so iOS does not zoom on focus; buttons, list rows and link chips are at least 44 px; text uses rem so it follows the system font size; the page has no horizontal scroll; both color schemes reuse the existing variables; animations are off under `prefers-reduced-motion`.

### 触摸操作 / Touch interaction

鼠标悬停的功能在触摸屏上用长按代替:在棋盘上按住约 0.3 秒,效果和鼠标悬停完全一样(只显示那个分支的预览、从 1 开始编号、颜色和 1 / a / i 层级规则都不变),手指在棋盘上滑动可以切换预览,松手立刻清除。短按的行为和点击一样:点蓝圈进入该分支,点 AI 候选点固定或取消固定它的变化。长按之后浏览器补发的点击会被吞掉,避免误进入分支。

Hover features become a long press on touch screens. Hold the board for about 0.3 seconds and you get exactly what a mouse hover gives: only that branch is previewed, numbering starts at 1, and the colors and the 1 / a / i hierarchy are unchanged. Sliding the finger over the board switches the preview and releasing clears it at once. A short tap behaves like a click: a blue circle enters the branch, an AI dot pins or unpins its line. The click that browsers send after a long press is swallowed so it cannot enter a branch by accident.

实现方式是把长按转成对棋盘原有鼠标处理函数的调用,所以悬停隔离、层级和颜色的规则只有一份代码。棋盘使用 `touch-action: none`,拖动不会滚动或缩放页面;触摸之后浏览器合成的鼠标事件会被忽略,避免出现幽灵悬停;双击缩放和手势缩放被禁止在棋盘上触发。鼠标的行为没有改动。

It works by turning the long press into a call of the board's existing mouse handlers, so the rules for hover isolation, levels and colors exist only once. The board uses `touch-action: none`, so dragging neither scrolls nor zooms the page; the mouse events that browsers synthesize after a touch are ignored so no ghost hover appears; double tap and gesture zoom are blocked on the board. Mouse behaviour is unchanged.

训练模式用两次点击答题:第一次点击在该点显示半透明的预览棋子并提示,第二次点击同一个位置才确认;点别处会改选。这样一次手滑不会直接交卷。

Training mode answers with two taps: the first tap shows a translucent preview stone and a hint, and only a second tap on the same point confirms; tapping elsewhere moves the mark. A slip of the finger therefore never submits an answer.

### 可安装的离线应用 / Installable offline app

新增 `manifest.webmanifest`、四个图标(`tools/make_icons.py` 用标准库画的棋盘一角和两颗棋子,没有外部素材)、`theme-color` 与 Apple 触摸图标标签,以及 `sw.js` 服务工作线程。`sw.js` 缓存页面外壳和 `data/library.js`,缓存名是 `joseki-shell-v` 加界面版本号;只处理同源 GET 请求,跨域请求(比如 bilibili 链接、你自己的引擎桥接)直接放行,从不缓存。

The change adds `manifest.webmanifest`, four icons (drawn by `tools/make_icons.py` with the standard library, a board corner and two stones, no outside artwork), `theme-color` and Apple touch icon tags, and the `sw.js` service worker. `sw.js` caches the page shell and `data/library.js` under the name `joseki-shell-v` plus the interface version. It handles same-origin GET requests only; cross-origin requests (such as bilibili links or your own engine bridge) pass through and are never cached.

外壳文件是缓存优先。`data/library.js` 由流水线重新生成而界面版本号不变,所以它也是先返回缓存、同时在后台刷新,下次打开就是新数据。更新流程是安全的:新版本安装后处于等待状态,页面底部出现「有新版本,点这里更新」,点击后才切换并刷新,正在使用的会话不会被替换。

Shell files are cache first. `data/library.js` is regenerated by the pipeline without a version bump, so it is served from the cache and refreshed in the background, and the next open has the new data. The update flow is safe: a new version waits after installing, a notice "有新版本,点这里更新" appears at the bottom, and the switch and reload happen only after a tap, so a running session is never replaced.

### 隐私测试的扩展 / The extended privacy test

原来的 `tests/privacy.test.js` 禁止 `engine_net.js` 以外的任何文件使用网络接口。现在有意识地放开两个文件,而且各有限制:`sw.js` 可以调用一次 `fetch`,并且必须在 `respondWith` 之前先判断同源、只处理 GET、不含任何绝对网址、不含其他网络接口;`pwa.js` 只允许出现 `navigator.serviceWorker`,没有任何网络调用,并且唯一的 `register` 调用只能写同目录的 `'sw.js'`。其余所有规则不变,另外有测试保证缓存名和界面版本号一致、外壳清单里的文件都存在(`tests/sw.test.js` 还用假的工作线程环境测了安装、激活、离线、更新等逻辑)。

The existing `tests/privacy.test.js` forbade network APIs in every file except `engine_net.js`. It now deliberately allows two files, each with limits. `sw.js` may call `fetch` once and must check the origin before `respondWith`, handle GET only, contain no absolute URL and no other network API. `pwa.js` may only name `navigator.serviceWorker`, has no network call at all, and its single `register` call may only name the same folder `'sw.js'`. All other rules are unchanged. More tests check that the cache name equals the interface version and that every file in the shell list exists. `tests/sw.test.js` also tests install, activate, offline, and the update handshake against a fake worker scope.

### 引擎面板与 https / Engine panel and https

手机上的 127.0.0.1 指的是手机自己,所以手机连不到电脑上的 KataGo。页面在算力卡片和 AI 推演卡片里显示这一说明;如果页面是通过 https 打开的,还会说明浏览器会拦截 http 开头的桥接地址(混合内容),应该使用 https 的远程 GPU 桥接地址。默认的「缓存」模式完全不联网,在手机和托管站点上都正常工作。

On a phone 127.0.0.1 means the phone itself, so a phone cannot reach KataGo on your computer. The compute card and the engine panel card say so, and when the page is opened over https they also explain that browsers block http bridge addresses (mixed content) and that an https remote GPU bridge address is needed. The default "cache" mode never touches the network and works on phones and on hosted sites.

### 设备矩阵 / Device matrix

下表是在浏览器窗格里用改变视口大小的方式检查的结果(CSS 像素)。检查项:没有横向滚动、棋盘大小、按钮和输入框的最小尺寸、控制栏位置、页脚可见。

The table shows what was checked in the browser pane by resizing the viewport (CSS pixels). Checks: no horizontal scroll, board size, minimum size of buttons and inputs, control bar position, footer visible.

| 视口 / Viewport | 模式 / Mode | 棋盘 / Board | 结果 / Result |
| --- | --- | --- | --- |
| 280x653 | 折叠屏外屏最窄 / narrowest cover screen | 280 px | 通过,控制栏可横向滑动 / pass, the bar scrolls sideways |
| 320x568 | 竖屏 / portrait | 292 px | 通过 / pass |
| 344x882 | 折叠屏外屏 / folded cover | 344 px | 通过 / pass |
| 360x740, 360x800 | 竖屏 / portrait | 360 px | 通过 / pass |
| 375x667 | 竖屏 / portrait | 375 px | 通过 / pass |
| 390x844 | 竖屏 / portrait | 390 px | 通过 / pass |
| 393x852 | 竖屏 / portrait | 393 px | 通过 / pass |
| 412x915 | 竖屏 / portrait | 412 px | 通过 / pass |
| 430x932 | 竖屏 / portrait | 430 px | 通过 / pass |
| 720x1080 | 折叠屏展开 / unfolded | 691 px | 通过 / pass |
| 768x1024, 820x1180, 1024x1366 | 平板竖屏 / tablet portrait | 窗口高度的 64%(1024x1366 为 874 px)/ 64% of the height (874 px at 1024x1366) | 通过 / pass |
| 568x320, 667x375, 800x360, 844x390, 882x344 | 横屏手机 / landscape phone | 窗口高度减页脚(280、335、320、350、304 px)/ height minus footer (280, 335, 320, 350, 304 px) | 通过 / pass |
| 1024x768, 1080x720, 1180x820 | 平板横屏 / tablet landscape | 窗口高度减页脚(728、680、780 px)/ height minus footer (728, 680, 780 px) | 通过 / pass |
| 1366x1024 及更宽 / and wider | 桌面 / desktop | 原样 / unchanged | 不变 / unchanged |

每一行都检查了:没有横向滚动、按钮和链接不小于 44 px、控制栏在窗口底部(横屏时在右栏底部)、页脚可见。真机、真实的 iOS Safari、捏合缩放和真实触摸事件没有在这个环境里测试过,见下一节。

Every row was checked for: no horizontal scroll, buttons and links of at least 44 px, the control bar at the bottom of the window (bottom of the right column in landscape), and a visible footer. Real devices, real iOS Safari, pinch zoom and real touch events were not tested in this environment, see the next section.

### 没有验证的内容 / What is not verified

浏览器窗格不能发出真实的触摸事件,所以长按和两次点击是用合成的 `PointerEvent`(`pointerType: touch`)测试的;捏合缩放、iOS Safari 的橡皮筋滚动、地址栏收起时的 `dvh` 变化、安全区的真实数值、Android 的返回键、从主屏幕启动的独立窗口,都没有测过。窗格也不允许注册服务工作线程,所以离线行为用 Docker 里的逻辑测试覆盖,没有在真实浏览器里断网重载。

The browser pane cannot send real touch events, so the long press and the double tap were tested with synthetic `PointerEvent`s (`pointerType: touch`). Pinch zoom, the iOS Safari rubber band, `dvh` changes while the address bar collapses, real safe area values, the Android back button and the standalone window launched from the home screen were not tested. The pane also does not allow registering a service worker, so the offline behaviour is covered by the logic test in Docker and was not tried with a real offline reload in a browser.

## 托管调研 / Hosting research

### 通用前提 / Common ground

老师的讲解文字不属于我们,可能迁出公开仓库。因此任何公开托管都应该使用 `--strip-commentary` 生成的站点:它保留要点、AI 评估、时间链接和视频链接,只去掉老师讲解的文字。「不公开的网址」不是秘密:任何人拿到链接都能打开,搜索引擎和链接预览也可能抓取它,所以 `_headers` 里加了 `X-Robots-Tag: noindex` 和 `robots.txt`,但这只是礼貌性的请求,不是访问控制。

The teacher's commentary text is not ours and may leave the public repository. Any public hosting should therefore use the site built with `--strip-commentary`: it keeps key points, AI evaluation, time links and video links and drops only the teacher's text. An unlisted URL is not a secret: anyone who gets the link can open it, and crawlers and link previews may fetch it. `_headers` adds `X-Robots-Tag: noindex` and there is a `robots.txt`, but that is a polite request and not access control.

### 境外:欧洲优先,其次北美 / Abroad: Europe first, then North America

| 服务 / Service | 免费额度 / Free limits | 欧洲边缘与数据 / EU edge and data | 私有仓库免费部署 / Private repo free | 访问控制 / Access control | 不用 CI 的部署 / Deploy without CI |
| --- | --- | --- | --- | --- | --- |
| GitHub Pages | 站点 1 GB、部署 10 分钟超时(官方企业版文档);带宽软限制 100 GB 每月(第三方,未核实) / site 1 GB, 10 minute deploy timeout (official enterprise docs); soft 100 GB per month bandwidth (third party, not verified) | 全球 CDN,无欧盟数据驻留承诺(未核实) / global CDN, no EU residency promise (not verified) | 不行,免费账号只能从公开仓库发布 / no, a Free account publishes from public repositories only | 站点本身无法设为私有,需要企业云(第三方文章) / the site cannot be made private without Enterprise Cloud (third party article) | 可以:选择「从分支部署」,不需要工作流 / yes, "deploy from a branch" needs no workflow |
| Cloudflare Pages | 免费版每站 20000 个文件、单文件 25 MiB、每月 500 次构建(官方) / Free: 20000 files per site, 25 MiB per file, 500 builds per month (official) | 全球 CDN,免费版没有欧盟限定(数据本地化套件为企业功能,未核实) / global CDN, no EU restriction on Free (Data Localization Suite is an enterprise feature, not verified) | 直接上传不需要任何仓库 / Direct Upload needs no repository at all | 没有一键密码;可用 Cloudflare Access(免费档的人数上限未核实) / no one click password; Cloudflare Access can protect it (free tier user cap not verified) | 可以:`wrangler pages deploy site/`(直接上传,官方文档) / yes: `wrangler pages deploy site/` (Direct Upload, official docs) |
| Netlify | 免费档含拖拽部署;额度计量方式近期有变,未核实 / free tier includes drag and drop; the quota metering changed recently, not verified | 免费档没有欧盟限定(数据分区属于高级档,第三方,未核实) / no EU restriction on free (data partition is a higher tier, third party, not verified) | 私有仓库可连接(未核实) / private repos can be connected (not verified) | 站点密码是付费功能(第三方,未核实) / site password is a paid feature (third party, not verified) | 可以:网页拖拽或 `netlify deploy` / yes: drag and drop or `netlify deploy` |
| Vercel | Hobby 档仅限个人非商业使用,商业定义较宽(第三方解读,未核实) / Hobby is personal non commercial use only, "commercial" is defined broadly (third party reading, not verified) | 无欧盟限定的免费选项(未核实) / no free EU only option (not verified) | 私有仓库可用(未核实) / private repos work (not verified) | Hobby 没有密码;免费的 Vercel 认证要求访客有 Vercel 账号(第三方) / no password on Hobby; the free Vercel Authentication needs every viewer to have a Vercel account (third party) | 可以:`vercel deploy` / yes: `vercel deploy` |
| GitLab Pages | 免费档可用(未核实具体额度) / available on Free (exact limits not verified) | GitLab.com 的数据位置未核实 / GitLab.com data location not verified | 可以,而且访问控制在免费档可用 / yes, and access control is available on Free | 私有项目可选「仅项目成员」(官方文档) / private projects can choose "only project members" (official docs) | 不太适合:发布通常需要 `.gitlab-ci.yml` 里的 pages 任务,也就是 CI(未核实) / poor fit: publishing normally needs a pages job in `.gitlab-ci.yml`, which is CI (not verified) |
| Codeberg Pages | 非营利、偏向开源项目,仅静态站点,体量要小;2025 年底条款更新并加了配额,数值未核实 / non profit, aimed at open source, static only and small; terms were extended in late 2025 with storage quotas, values not verified | 德国非营利组织(未核实具体机房) / German non profit (exact data centre not verified) | 页面内容需要在公开的 pages 分支上,未核实私有仓库是否可用 / content sits on a public pages branch, private repo use not verified | 无 / none | 可以:推送到 `pages` 分支,不需要 CI(官方文档方式) / yes: push to the `pages` branch, no CI |
| Firebase Hosting | Spark 免费档约 10 GB 存储、每天 360 MB 传输(第三方汇总) / Spark free about 10 GB storage and 360 MB per day transfer (third party summaries) | 可选多区域,免费档是否能限定欧盟未核实 / multi region, whether Free can pin to the EU is not verified | 命令行直接上传,不需要仓库 / CLI upload needs no repository | 无内置密码(未核实) / no built in password (not verified) | 可以:`firebase deploy` / yes: `firebase deploy` |
| Azure Static Web Apps | 有免费档,具体额度和密码保护是否在免费档未核实 / a Free plan exists, exact limits and whether password protection is on it are not verified | 可选欧洲区域(未核实) / European regions available (not verified) | 命令行部署可以不用仓库(未核实) / CLI deploy can work without a repository (not verified) | 未核实 / not verified | `swa deploy`(未核实) / `swa deploy` (not verified) |
| statichost.eu | 免费档每月 100 分钟构建、10 GB 流量,超出按量计费(官方定价页摘要) / free tier 100 build minutes and 10 GB traffic per month, overage billed (pricing page snippet) | 瑞典公司,声称全程使用欧洲基础设施,不用 AWS 和 Cloudflare(自述;目录站点显示机房在法国,未核实) / Swedish company, says the whole stack is European and uses neither AWS nor Cloudflare (self description; a directory shows a French data centre, not verified) | 官方文档里的上传方式未核实 / upload methods in its docs not verified | 未核实 / not verified | 未核实,官网文档有说明 / not verified, see its docs |
| IONOS Deploy Now | 欧洲替代品目录列出,免费额度未核实 / listed in a European alternatives directory, free limits not verified | 德国公司(目录列出) / German company (directory listing) | 未核实 / not verified | 未核实 / not verified | 未核实 / not verified |

来源:[GitHub Pages 限制(企业版文档)](https://docs.github.com/en/enterprise-server@3.15/pages/getting-started-with-github-pages/github-pages-limits)、[2026 年关于私有仓库的说明(第三方)](https://smartscope.blog/Tips/GitHub/github-pages-private-repository/)、[Cloudflare Pages 限制](https://developers.cloudflare.com/pages/platform/limits)、[Cloudflare 直接上传](https://developers.cloudflare.com/pages/platform/direct-upload/)、[GitLab Pages 访问控制](https://docs.gitlab.com/user/project/pages/pages_access_control.html)、[Netlify 与 Vercel 对比(第三方)](https://cmaven.github.io/en/hosting/netlify-vercel-static-hosting-comparison/)、[Netlify Drop 与 Vercel Drop(Netlify 自己的对比页)](https://www.netlify.com/knowledge-base/netlify-drop-vs-vercel-drop/)、[Codeberg Pages 讨论(第三方)](https://discuss.privacyguides.net/t/web-hosting-for-basic-website/15008/10)、[Firebase Hosting 汇总(第三方)](https://freetier.co/directory/products/firebase-hosting)、[statichost.eu](https://statichost.eu/pricing)、[欧洲替代品目录](https://european-alternatives.eu/alternative-to/netlify)。

Sources: [GitHub Pages limits (enterprise docs)](https://docs.github.com/en/enterprise-server@3.15/pages/getting-started-with-github-pages/github-pages-limits), [2026 note on private repositories (third party)](https://smartscope.blog/Tips/GitHub/github-pages-private-repository/), [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits), [Cloudflare Direct Upload](https://developers.cloudflare.com/pages/platform/direct-upload/), [GitLab Pages access control](https://docs.gitlab.com/user/project/pages/pages_access_control.html), [Netlify and Vercel comparison (third party)](https://cmaven.github.io/en/hosting/netlify-vercel-static-hosting-comparison/), [Netlify Drop and Vercel Drop (Netlify's own comparison page)](https://www.netlify.com/knowledge-base/netlify-drop-vs-vercel-drop/), [Codeberg Pages discussion (third party)](https://discuss.privacyguides.net/t/web-hosting-for-basic-website/15008/10), [Firebase Hosting summary (third party)](https://freetier.co/directory/products/firebase-hosting), [statichost.eu](https://statichost.eu/pricing), [European alternatives directory](https://european-alternatives.eu/alternative-to/netlify).

隐私和 GDPR 提示:站点是纯静态的,没有统计脚本、没有 cookie,页面不会向作者发送任何数据(见 `tests/privacy.test.js`)。托管服务商仍然会在服务器日志里看到访客的 IP 地址和请求的文件名,这属于服务商作为处理者的日常日志;如果面向欧盟访客公开,建议选用有数据处理协议的服务商,并在页面或 README 里说明这一点。这不是法律意见。

Privacy and GDPR note: the site is purely static with no analytics script and no cookie, and the page sends nothing to the author (see `tests/privacy.test.js`). The host still sees visitor IP addresses and requested file names in its server logs, which is ordinary processor logging. If the site is public to EU visitors, prefer a provider with a data processing agreement and say so on the page or in the README. This is not legal advice.

欧洲优先的建议:想要最省事,用 Cloudflare Pages 的直接上传加 `--strip-commentary`,不需要仓库、不需要 CI,全球节点对欧洲访问快;如果要求服务商和基础设施都在欧洲,选 statichost.eu,或者非营利的 Codeberg Pages(仅适合开源性质的小站点,要先读它的条款)。想要「只有自己和朋友能看」,用 Cloudflare Access 或 GitLab Pages 的「仅项目成员」,而不要依赖不公开的网址。

Recommendation for Europe first: for the least effort use Cloudflare Pages Direct Upload with `--strip-commentary`: no repository and no CI needed, and its worldwide edge is fast for Europe. If the provider and the infrastructure must be European, choose statichost.eu, or the non profit Codeberg Pages (only for small open source style sites, read its terms first). To restrict the site to yourself and friends use Cloudflare Access or GitLab Pages "only project members", and do not rely on an unlisted URL.

北美的建议:同样优先 Cloudflare Pages 直接上传;Netlify 的拖拽部署是同样省事的备选;Vercel Hobby 只限个人非商业使用,本项目的许可证本身是非商业的,但是否符合它对「商业」的定义要自己读条款;GitHub Pages 只在仓库公开时免费,而公开仓库不应包含老师的讲解文字。

Recommendation for North America: again prefer Cloudflare Pages Direct Upload; Netlify drag and drop is an equally easy alternative. Vercel Hobby is for personal non commercial use: this project's license is non commercial, but check yourself whether it fits Vercel's definition of "commercial". GitHub Pages is free only for public repositories, and a public repository should not contain the teacher's commentary text.

### 中国大陆 / Mainland China

| 方案 / Option | 现状与限制 / Status and limits | 是否需要备案 / Filing needed |
| --- | --- | --- |
| Gitee Pages | 历来要求实名认证才能使用;有人称它被无通知下线,但没有官方公告,当前状态未核实 / historically needs real name verification; one report says it was taken offline without notice, no official notice found, current status not verified | 未核实 / not verified |
| 腾讯云开发 CloudBase 静态托管 | 有免费默认域名和限时免费额度的说法(2020 年文章);另有 2021 年说法称托管域名不再支持备案,以及自定义域名需要已备案。当前规则未核实 / reports of a free default domain and a limited free quota (2020 article); a 2021 report says hosted domains no longer support filing and custom domains need a filed domain. Current rules not verified | 自定义域名在境内节点需要 ICP 备案(未核实) / a custom domain on a mainland node needs ICP filing (not verified) |
| 阿里云 OSS 静态网站托管 | 境内地域的存储桶绑定自定义域名需要备案;这一点来自阿里云备案文档的一般说明,OSS 的具体免费额度未核实 / for a mainland region bucket a custom domain needs filing, from the general Alibaba Cloud filing docs; OSS free quota not verified | 境内节点需要 ICP 备案;中国香港节点不需要 ICP 备案但仍需公安联网备案(阿里云文档) / mainland nodes need ICP filing; a Hong Kong node needs no ICP filing but still the public security filing (Alibaba Cloud docs) |
| 百度、腾讯 EdgeOne Pages 等 | 有人提到腾讯 EdgeOne Pages 面向中国访客,但只是论坛说法,条款和额度未核实 / a forum mentions Tencent EdgeOne Pages for Chinese visitors, only a forum claim, terms and quota not verified | 未核实 / not verified |
| Cloudflare Pages | 官方没有说被封锁,但论坛用户称访问时断时续,企业版加中国域名解析才稳定(未核实) / no official statement of a block, but forum users report intermittent access and say it needs Enterprise with Chinese DNS to be stable (not verified) | 不需要,因为服务器在境外 / no, the servers are abroad |
| GitHub Pages | 论坛称在大陆时断时续,速度不理想(用户观察,未核实) / forum users say access is intermittent and slow (user observation, not verified) | 不需要 / no |
| Netlify | 在大陆没有节点,第三方测得延迟超过 3000 ms(日期不明,未核实) / no mainland nodes, a third party measured over 3000 ms latency (date unknown, not verified) | 不需要 / no |
| Vercel | 官方承认在大陆可能变慢或连不上,`.vercel.app` 可能被限制,建议用自己的域名(官方指南);境内部署需要 ICP 备案 / Vercel itself says sites may be slow or unreachable in the mainland, `.vercel.app` may be restricted, and recommends your own domain (official guide); mainland hosting needs ICP filing | 境外托管不需要 / not for overseas hosting |

来源:[Vercel 官方指南:从中国大陆访问](https://vercel.com/guides/accessing-vercel-hosted-sites-from-mainland-china)、[阿里云备案常见问题](https://help.aliyun.com/zh/dws/faq-about-icp-filing)、[阿里云 ICP 备案页](https://www.alibabacloud.com/zh/icp)、[少数派对腾讯云开发静态托管的介绍(2020)](https://sspai.com/post/60264)、[LowEndSpirit 上的 EdgeOne Pages 讨论(论坛)](https://lowendspirit.com/discussion/8352)、[一个提到 Gitee Pages 下线的 issue 评论(无日期,未核实)](https://www.github.com/g1879/DrissionPage/issues/229)。

Sources: [Vercel official guide: accessing from mainland China](https://vercel.com/guides/accessing-vercel-hosted-sites-from-mainland-china), [Alibaba Cloud ICP filing FAQ](https://help.aliyun.com/zh/dws/faq-about-icp-filing), [Alibaba Cloud ICP page](https://www.alibabacloud.com/zh/icp), [sspai on Tencent CloudBase static hosting (2020)](https://sspai.com/post/60264), [EdgeOne Pages discussion on LowEndSpirit (forum)](https://lowendspirit.com/discussion/8352), [an issue comment that mentions Gitee Pages going offline (undated, not verified)](https://www.github.com/g1879/DrissionPage/issues/229).

不备案能做到什么:服务器放在境外或中国香港的站点不需要工信部 ICP 备案,境内用户可以尝试访问,但没有任何到达性保证,速度和稳定性随网络环境变化。要在境内机房托管,个人网站也需要先完成 ICP 备案,而且已备案的域名如果改绑到境外节点,备案可能被注销(阿里云文档)。

What works without filing: a site hosted abroad or in Hong Kong needs no MIIT ICP filing and users in the mainland can try to open it, but there is no reachability guarantee and speed and stability vary with the network. Hosting in a mainland data centre needs ICP filing even for a personal site, and a filed domain that is moved to an overseas node may lose its filing (Alibaba Cloud docs).

中国大陆的现实建议:没有备案的前提下,最稳妥的办法是把站点当作可安装的离线应用:用能访问的网络安装一次(添加到主屏幕),之后离线使用,不再依赖网络;或者把 `site/` 文件夹打包直接发给对方,在电脑上用本地服务器打开(`file://` 不能注册服务工作线程)。其次是 Cloudflare Pages 加自己的域名并带 `--strip-commentary`,再让对方自行测试可达性。要面向大陆长期公开,才需要认真考虑备案加境内托管,这需要实名和境内手机号等材料,我没有核实具体流程。

Realistic recommendation for mainland China: without filing, the safest way is to treat the site as an installable offline app: install it once over a network that can reach it (add to home screen), then use it offline without depending on the network, or zip the `site/` folder and send it so the other person opens it with a local server on a computer (`file://` cannot register a service worker). The second choice is Cloudflare Pages with your own domain and `--strip-commentary`, and ask the other person to test reachability. Only a long term public site for the mainland needs filing plus mainland hosting seriously; that needs real name and a mainland phone number and similar documents, and I did not verify the exact process.

## 准备好的托管布局 / Prepared hosting layout

`tools/make_site.py` 只用标准库,生成可以直接上传的 `site/` 文件夹:`index.html`、各个脚本、`manifest.webmanifest`、`sw.js`、`icons/`、`data/library.js`、`_headers`(Cloudflare Pages 和 Netlify 通用)、`robots.txt` 和一个说明文件。不需要重定向文件,所以没有生成 `_redirects`。`_headers` 里的内容安全策略用哈希放行页面里唯一的内联脚本,所以脚本不需要 `unsafe-inline`;`connect-src` 允许 https 和本机回环地址,是为了让用户自己的引擎桥接可以工作,如果不需要引擎功能,可以改成只有 `'self'`。

`tools/make_site.py` uses only the standard library and builds an upload ready `site/` folder: `index.html`, the scripts, `manifest.webmanifest`, `sw.js`, `icons/`, `data/library.js`, `_headers` (shared by Cloudflare Pages and Netlify), `robots.txt` and a readme. No redirects are needed, so no `_redirects` file is written. The Content Security Policy in `_headers` allows the one inline script of the page by hash, so scripts need no `unsafe-inline`. `connect-src` allows https and the loopback addresses so a user's own engine bridge can work; if the engine feature is not wanted, reduce it to `'self'` only.

加上 `--strip-commentary` 时,库里每个 SGF 注释中以「【老师讲解」开头的段落只保留标题和时间链接(如 `【老师讲解 @0|0:30】`),正文换成一句提示;要点、AI 评估、周边说明等其他段落原样保留。源文件 `data/library.js` 不会被修改。`--library-only 文件` 只生成一份去掉讲解文字的库文件。脚本和测试都不会上传任何东西。

With `--strip-commentary`, in every SGF comment the paragraphs that begin with "【老师讲解" keep only the header and the time link (such as `【老师讲解 @0|0:30】`) and the body is replaced by a short notice. Key points, AI evaluation, context notes and all other sections are kept as they are. The source `data/library.js` is never modified. `--library-only FILE` writes just a library without the teacher text. Neither the script nor its tests upload anything.

```
python tools/make_site.py --strip-commentary --out site
python tools/make_site.py --library-only library.stripped.js --strip-commentary
```

在 Docker 里运行脚本和测试(不用 venv):

Run the script and its tests in Docker (no venv):

```
docker run --rm -v "$PWD:/app" -w /app python:3.12-slim python -I tools/make_site.py --strip-commentary --out /tmp/site
docker run --rm -v "$PWD:/app" -w /app python:3.12-slim sh -c "pip install -q --root-user-action=ignore pytest && python -m pytest -q tests/test_make_site.py"
```

以下命令只是准备好的记录,没有执行过,而且每条都会让站点变成公开可访问,所以要等你决定之后再执行:

The commands below are only prepared notes. They were never run, and each one makes the site reachable, so run them only after you decide:

```
npx wrangler pages deploy site/ --project-name <name>      # Cloudflare Pages, Direct Upload
npx netlify deploy --dir site --prod                       # Netlify
```
