MiniMax API base URL: https://api.minimaxi.com/v1
§
用户（佳哥）对信息获取的要求：对数据敏感、对内容采集严谨、对分析有理有据。使用最可信的数据源，对所有引用进行标注。这是最高优先级的工作标准。
§
社媒平台抓取需要授权时，必须将二维码返回给佳哥扫码，不能自行授权。所有抓取数据必须全部存入数据库，为后续分析服务。后续从本地数据库挖掘时，使用向量匹配 vector_search 而非 keyword_search 获取最相关内容。
§
§
文件夹结构文档已建立：/app/.hermes/STRUCTURE.md（含完整目录规范、Skills三层结构、产出路径规范）
§
Skills三层结构：用户级~/.hermes/skills/（可写） > 内置hermes-agent/skills/（只读） > 可选optional-skills/（需启用）
用户自建Skills：competitor-discovery、feeds、skill-creator、web、data-science/sentiment-data-collection、devops/wsl-windows-filesystem
§
技能索引缓存已迁移：hermes-agent/skills/index-cache/ → ~/.hermes/cache/skills_index-cache/
curator_state已迁移：~/.hermes/skills/.curator_state → ~/.hermes/curator_state
§
Scrapling 完整可用（2026-05-10）：Fetcher（HTTP+TLS指纹）+ StealthyFetcher（Chromium+JS渲染+Cloudflare绕过）。已装依赖：libnspr4 libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libcairo2(手动deb) libpango-1.0-0 libpixman-1-0 libxcb-shm0 libxcb-render0
§
本地文件操作根目录：/mnt/d/ (Windows D:)。所有本地文件读写操作都在此路径下进行。
§
已学Skills核心（97个总）：`radar-engine`(舆情)、`keyword-research`(GEO)、`content-research-writer`(内容)、`web-access`(联网+CDP)、`skill-creator`(创建)、`python-debugpy`、`systematic-debugging`、`scrapling-web-scraper`(反爬)。Skills路径：/app/.hermes/skills/用户级 + /app/hermes-agent/skills/内置。
§
Skill Discovery 技巧（2026-05-09 学会）：skill_view 中文名失败时 → terminal find /app/.hermes/skills/ -maxdepth 3 -type d | sort 定位真实路径 + 检查 name mapping（内部slug可能与显示名不同，如 sentiment-data-collection ≠ 舆情数据采集规范）。参考：/app/.hermes/skills/skill-creator/references/skill-discovery.md
§
GEO研究项目文件夹规范（2026-05-10）：每个项目单独建文件夹 /桂格麦片-GEO/{urls/,report/,data/}，产出两个文档：(1)数据源URL列表 (2)完整GEO报告。数据优先从本地向量数据库挖掘（keyword_search/get_recent_data），不足时再补充web搜索。
§
所有产出文档必须放到 /app/final_reports/（即 Windows D:\），用户可直接通过文件资源管理器访问。后续GEO研究报告、竞品分析等产出均以此为基准路径。
§
Scrapling完整可用（2026-05-10）：Fetcher（HTTP+TLS指纹）+ StealthyFetcher（Chromium+JS渲染+Cloudflare绕过+adaptive解析）。系统依赖已全装。关键API：r.status（不是r.status_code），StealthyFetcher.fetch()类方法（不是.get()）。