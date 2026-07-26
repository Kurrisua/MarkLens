"""Idempotent demo dataset and verified legal-source seed command."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .config import get_settings
from .db import get_session_factory
from .models import (
    AgentRun,
    CaseRecord,
    Consultation,
    DocumentDraft,
    ImageAsset,
    LearningArticle,
    LearningTopic,
    LearningVideo,
    LegalChunk,
    LegalSource,
    PracticeQuestion,
    Project,
    RiskAnalysis,
    SearchRecord,
    SourceDefinition,
    Trademark,
    TrademarkFeature,
    User,
    UserRole,
)
from .retrieval import LocalModelRuntime, process_image, vector_to_blob
from .sources import ensure_source_definitions, sync_source

DEMO_NAMES = [
    "MarkLens",
    "MarkLink",
    "MarkSense",
    "马克视界",
    "马克透镜",
    "标镜",
    "标识之眼",
    "商标雷达",
    "BrandLens",
    "LogoLens",
    "蓝镜",
    "蓝标",
    "明标",
    "知标",
    "标智",
    "标盾",
    "法镜",
    "法眼标识",
    "知产镜",
    "知产雷达",
    "云标",
    "云标智检",
    "图标通",
    "图形之眼",
    "商标智库",
    "商标卫士",
    "商标先锋",
    "商标管家",
    "品牌罗盘",
    "品牌哨兵",
    "品牌视窗",
    "品牌之眼",
    "品牌卫士",
    "品牌盾",
    "标律",
    "标法通",
    "标法云",
    "法务智标",
    "法商镜",
    "权利之镜",
    "权盾",
    "知权",
    "知产卫士",
    "IP Lens",
    "IP Radar",
    "Trademark Lens",
    "TradeMark AI",
    "MarkScope",
    "MarkGuard",
    "MarkPilot",
    "MarkWatch",
    "MarkWise",
    "BrandScope",
    "BrandGuard",
    "BrandPilot",
    "LogoGuard",
    "LogoScope",
    "商标小镜",
    "标小智",
    "标查查",
]

GOODS_BY_CLASS = {
    9: ["可下载的计算机软件", "图像识别软件", "数据处理设备"],
    35: ["商业信息服务", "市场分析", "广告策划"],
    42: ["软件即服务", "计算机软件设计", "人工智能技术咨询"],
    45: ["知识产权咨询", "法律研究", "知识产权许可"],
}

LAW_SEEDS = [
    {
        "title": "中华人民共和国商标法（2019年修正）",
        "authority": "全国人民代表大会常务委员会",
        "source_url": "https://flk.npc.gov.cn/detail?fileId=&id=ff8080816f135f46016f217645451b35&title=%E4%B8%AD%E5%8D%8E%E4%BA%BA%E6%B0%91%E5%85%B1%E5%92%8C%E5%9B%BD%E5%95%86%E6%A0%87%E6%B3%95&type=",
        "source_type": "law",
        "version_label": "2019年修正现行商标法",
        "effective_from": date(2019, 11, 1),
        "effective_to": date(2026, 12, 31),
        "sections": [
            (
                "第三十条",
                "申请注册的商标，凡不符合本法有关规定，或者同他人在同一种商品或者类似商品上已经注册的或者初步审定的商标相同或者近似的，由商标局驳回申请，不予公告。",
            ),
            (
                "第三十一条",
                "两个或者两个以上的商标注册申请人，在同一种商品或者类似商品上，以相同或者近似的商标申请注册的，初步审定并公告申请在先的商标；同一天申请的，初步审定并公告使用在先的商标，驳回其他人的申请，不予公告。",
            ),
            (
                "第三十二条",
                "申请商标注册不得损害他人现有的在先权利，也不得以不正当手段抢先注册他人已经使用并有一定影响的商标。",
            ),
            (
                "第五十七条",
                "在同一种商品上使用与注册商标相同的商标，以及未经许可在同一种或类似商品上使用与注册商标相同或近似且容易导致混淆的商标，属于侵犯注册商标专用权的情形。",
            ),
        ],
    },
    {
        "title": "商标审查审理指南（2021）",
        "authority": "国家知识产权局",
        "source_url": "https://www.cnipa.gov.cn/art/2021/11/22/art_74_171575.html",
        "source_type": "examination_guide",
        "version_label": "2021年商标审查审理指南",
        "effective_from": date(2022, 1, 1),
        "effective_to": None,
        "sections": [
            (
                "近似商标判断概述",
                "近似判断通常结合商标标志本身的音、形、义和整体表现形式，考虑指定使用商品或服务的类似关系，并以相关公众的一般注意力为判断基础。",
            ),
            (
                "文字商标审查要点",
                "文字商标应比较字形、读音、含义、文字排列和整体视觉效果。局部差异并不当然排除相关公众产生来源误认的可能。",
            ),
            (
                "图形商标审查要点",
                "图形商标通常比较构图、表现手法和整体视觉印象。共同显著部分可能影响近似判断，但仍需结合具体商品服务和标志整体。",
            ),
            (
                "组合商标审查要点",
                "组合商标中的文字、图形等构成要素可能分别影响识别。判断应关注主要识别部分和整体是否容易造成商品或服务来源混淆。",
            ),
        ],
    },
    {
        "title": "商标侵权判断标准",
        "authority": "国家知识产权局",
        "source_url": "https://www.cnipa.gov.cn/art/2020/6/17/art_75_126939.html",
        "source_type": "administrative_standard",
        "version_label": "国知发保字〔2020〕23号",
        "effective_from": date(2020, 6, 17),
        "effective_to": None,
        "sections": [
            (
                "第九条至第十二条 商品服务类似判断",
                "判断商品是否相同或类似，应比较功能、用途、主要原料、生产部门、消费对象和销售渠道等因素；判断服务是否相同或类似，应比较服务目的、内容、方式、提供者、对象和场所等因素。类似商品和服务区分表是重要参考，但未涵盖项目仍应结合相关公众的一般认识综合判断。",
            ),
            (
                "第十五条 标志近似类型",
                "文字商标应关注字形、读音和含义，图形商标应关注构图、着色和外形，文字图形组合商标应关注整体排列组合方式和外形。立体、颜色组合及声音商标还应分别比较其主要视觉或听觉印象。",
            ),
            (
                "第十八条至第二十一条 比对方法与混淆因素",
                "标志比对应以相关公众的一般注意力和认知力为标准，采用隔离观察、整体比对和主要部分比对。判断混淆可能性时，应综合考虑标志近似情况、商品服务类似情况、注册商标显著性和知名度、商品服务特点、商标使用方式以及相关公众的注意和认知程度。混淆既包括对商品服务来源的误认，也包括对投资、许可、加盟或合作关系的误认。",
            ),
        ],
    },
    {
        "title": "最高人民法院关于审理商标授权确权行政案件若干问题的规定",
        "authority": "最高人民法院",
        "source_url": "https://gongbao.court.gov.cn/Details/24b8d167656cee1b3329634dcefaa6.html",
        "source_type": "judicial_interpretation",
        "version_label": "2020年修正",
        "effective_from": date(2017, 3, 1),
        "effective_to": None,
        "sections": [
            (
                "第十二条 混淆可能性综合因素",
                "在商标授权确权案件的特定保护情形中，混淆可能性需要综合考量标志近似程度、商品类似程度、请求保护商标的显著性和知名程度、相关公众注意程度及其他因素。申请人的主观意图和实际混淆证据可以作为参考。各项因素应结合具体事实相互影响地评价，不能由单一因素直接替代整体判断。",
            ),
            (
                "第二十一条 字号等在先权益",
                "具有一定市场知名度的字号或已经与企业建立稳定对应关系的企业名称简称，若被他人申请为相同或近似商标并容易导致相关公众对商品来源产生混淆，可以作为在先权益获得保护。",
            ),
        ],
    },
    {
        "title": "中华人民共和国商标法（2026年修订，未来生效版本）",
        "authority": "全国人民代表大会常务委员会",
        "source_url": "https://www.cnipa.gov.cn/col/col3684/index.html",
        "source_type": "law",
        "version_label": "2026年修订商标法（2027-01-01起施行）",
        "effective_from": date(2027, 1, 1),
        "effective_to": None,
        "sections": [
            (
                "版本适用提示",
                "本资料记录未来生效版本。分析日期早于2027年1月1日时不得作为现行法依据，具体条文应以官方公布文本为准。",
            ),
        ],
    },
]

LEARNING_LIBRARY = {
    "trademark-basics": {
        "prefix": "商标基础",
        "subjects": [
            "商标与企业名称的区别",
            "商标与商品名称的区别",
            "显著性的基本含义",
            "文字商标的构成",
            "图形商标的构成",
            "组合商标的识别重点",
            "颜色组合的使用边界",
            "声音标志的特殊性",
            "通用名称风险",
            "描述性表达风险",
        ],
        "angles": [
            "先判断什么",
            "容易忽略的事实",
            "面向创业者的提醒",
            "常见误区",
            "完成初筛后的下一步",
            "适合记录在项目里的信息",
            "判断时不能只看什么",
            "为什么需要人工复核",
            "和类别选择的关系",
            "一个简短练习",
        ],
    },
    "similarity": {
        "prefix": "近似判断",
        "subjects": [
            "文字字形比较",
            "读音比较",
            "含义比较",
            "整体视觉印象",
            "主要识别部分",
            "图形构图比较",
            "商品服务类似关系",
            "相关公众注意力",
            "隔离观察方法",
            "在先申请时间",
        ],
        "angles": [
            "为什么不能单独判断",
            "需要收集哪些证据",
            "常见的片面判断",
            "与类别的联动",
            "案例拆解方法",
            "结果出现分歧时怎么办",
            "初筛分数如何理解",
            "应当反向核查什么",
            "给名称修改的启发",
            "一个判断练习",
        ],
    },
    "application-path": {
        "prefix": "注册流程",
        "subjects": [
            "品牌命名准备",
            "尼斯类别选择",
            "近似检索准备",
            "申请材料准备",
            "形式审查阶段",
            "实质审查阶段",
            "初步审定公告",
            "异议期",
            "核准注册",
            "注册后的规范使用",
        ],
        "angles": [
            "这一阶段的目标",
            "需要留存的材料",
            "最常见的遗漏",
            "给项目负责人的提醒",
            "何时需要专业协助",
            "如何降低返工成本",
            "和前一步的衔接",
            "对未来业务的影响",
            "应当记录的时间点",
            "一个行动清单",
        ],
    },
}


def _learning_items(slug: str) -> list[tuple[str, str]]:
    library = LEARNING_LIBRARY[slug]
    items: list[tuple[str, str]] = []
    for subject_index, subject in enumerate(library["subjects"], start=1):
        for angle_index, angle in enumerate(library["angles"], start=1):
            number = (subject_index - 1) * len(library["angles"]) + angle_index
            title = f"{number:03d} · {subject}：{angle}"
            body = (
                f"{subject}不是一个可以脱离业务场景单独回答的问题。学习时先把拟使用的名称、"
                f"商品或服务、目标用户、使用方式和计划时间写清楚，再围绕“{angle}”逐项核对。"
                "系统的学习卡片只帮助你建立判断框架：它提示你需要比较哪些事实、哪些信息仍然缺失，"
                "而不是替你作出可以注册或一定不能注册的结论。完成本条后，请在自己的品牌项目中记下一项"
                "可验证信息，并在需要时结合官方查询结果或专业意见继续复核。"
            )
            items.append((title, body))
    return items


def _practice_items() -> list[dict[str, object]]:
    scenarios = [
        "儿童智能手表与配套应用",
        "餐饮品牌与外卖服务",
        "人工智能软件服务",
        "护肤品与零售服务",
        "咖啡品牌与咖啡馆服务",
        "运动服饰与线上销售",
        "家居用品与电商店铺",
        "宠物用品与诊疗服务",
        "教育课程与培训服务",
        "文创产品与展览活动",
    ]
    focuses = [
        "文字与读音",
        "图形与整体印象",
        "商品服务关联",
        "在先申请时间",
        "显著性与描述性",
        "类别覆盖范围",
        "使用证据",
        "修改方案比较",
        "检索结果的反向证据",
        "人工复核边界",
    ]
    items: list[dict[str, object]] = []
    for scenario_index, scenario in enumerate(scenarios, start=1):
        for focus_index, focus in enumerate(focuses, start=1):
            number = (scenario_index - 1) * len(focuses) + focus_index
            items.append(
                {
                    "title": f"实训 {number:03d} · {scenario}",
                    "prompt": f"某团队准备经营“{scenario}”。在进行“{focus}”的初步判断时，以下哪一种做法更稳妥？",
                    "options": [
                        {"id": "a", "label": "只依据名称是否完全相同，立即作出结论"},
                        {
                            "id": "b",
                            "label": "记录业务事实，综合比较候选证据，并标记需要进一步复核的部分",
                        },
                        {"id": "c", "label": "只要属于不同类别，就不再查看其他信息"},
                    ],
                    "correct_option": "b",
                    "explanation": "初筛应先保留事实和证据链，再综合判断文字、图形、商品服务及时间等因素。单一线索不能替代完整复核。",
                    "difficulty": "basic"
                    if number <= 34
                    else ("intermediate" if number <= 67 else "advanced"),
                }
            )
    return items


def _demo_records() -> list[dict[str, object]]:
    applicants = [
        "上海澄蓝科技有限公司",
        "杭州知权信息技术有限公司",
        "北京镜界数据有限公司",
        "深圳标识科技有限公司",
    ]
    statuses = ["已注册", "初步审定", "申请中", "无效"]
    records = []
    for index, name in enumerate(DEMO_NAMES, start=1):
        main_class = [9, 35, 42, 45][(index - 1) % 4]
        classes = [main_class]
        if index <= 18:
            classes = sorted(set([9, 42, main_class]))
        records.append(
            {
                "source_record_id": f"DEMO-{index:04d}",
                "name": name,
                "application_number": f"MLDEMO2026{index:05d}",
                "applicant": applicants[(index - 1) % len(applicants)],
                "nice_classes": classes,
                "goods_services": GOODS_BY_CLASS[main_class],
                "status": statuses[(index - 1) % len(statuses)],
                "status_date": f"202{2 + index % 4}-0{1 + index % 8}-15",
                "application_date": f"202{1 + index % 4}-0{1 + index % 8}-01",
                "source_url": f"demo://marklens/trademarks/DEMO-{index:04d}",
                "image_path": f"demo-logos/logo-{index:02d}.png" if index <= 12 else None,
                "is_demo": True,
                "data_notice": "合成教学数据，不对应真实商标权利。",
            }
        )
    return records


def prepare_demo_files() -> None:
    settings = get_settings()
    settings.source_data_dir.mkdir(parents=True, exist_ok=True)
    demo_path = settings.source_data_dir / "demo-trademarks.json"
    demo_path.write_text(
        json.dumps(_demo_records(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    csv_path = settings.source_data_dir / "demo-import.csv"
    csv_path.write_text(
        "source_record_id,name,application_number,applicant,nice_classes,goods_services,status,source_url,is_demo\n"
        "CSV-001,检标云,MLCSV0001,MarkLens课程组,9|42,软件即服务|图像识别软件,申请中,demo://marklens/csv/1,true\n"
        "CSV-002,知标镜,MLCSV0002,MarkLens课程组,45,知识产权咨询,已注册,demo://marklens/csv/2,true\n",
        encoding="utf-8",
    )


def _logo_bytes(index: int, label: str) -> bytes:
    from io import BytesIO

    palettes = [
        ("#17345f", "#eef4ff"),
        ("#275bb6", "#f3f7ff"),
        ("#30445f", "#f1f4f7"),
        ("#145d67", "#effafa"),
        ("#6b3d47", "#fff4f5"),
        ("#4c5278", "#f5f5ff"),
    ]
    foreground, background = palettes[(index - 1) % len(palettes)]
    image = Image.new("RGB", (720, 480), background)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=64)
    short = (
        "".join(character for character in label.upper() if character.isascii())[:4] or f"M{index}"
    )
    draw.rounded_rectangle((72, 72, 648, 408), radius=52, outline=foreground, width=14)
    draw.ellipse((130, 120, 370, 360), outline=foreground, width=18)
    draw.line((330, 320, 480, 400), fill=foreground, width=24)
    draw.text((405, 200), short, fill=foreground, font=font, anchor="mm")
    output = BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def seed_demo_assets(session: Session) -> None:
    settings = get_settings()
    logo_dir = settings.source_data_dir / "demo-logos"
    logo_dir.mkdir(parents=True, exist_ok=True)
    runtime = LocalModelRuntime(settings)
    trademarks = list(
        session.scalars(select(Trademark).where(Trademark.source_record_id.like("DEMO-%"))).all()
    )
    by_record = {item.source_record_id: item for item in trademarks}
    for index, name in enumerate(DEMO_NAMES[:12], start=1):
        content = _logo_bytes(index, name)
        processed = process_image(content, f"logo-{index:02d}.png", settings)
        storage_key = f"demo-logos/logo-{index:02d}.png"
        full_path = settings.upload_dir / storage_key
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(processed.content)
        asset = session.scalar(select(ImageAsset).where(ImageAsset.sha256 == processed.sha256))
        if asset is None:
            asset = ImageAsset(
                storage_key=storage_key,
                original_filename=f"demo-logo-{index:02d}.png",
                mime_type=processed.mime_type,
                sha256=processed.sha256,
                byte_size=len(processed.content),
                width=processed.width,
                height=processed.height,
                ocr_text=None,
                ocr_confidence=None,
                ocr_model="demo-none",
                phash=processed.phash,
                is_demo=True,
            )
            session.add(asset)
            session.flush()
        trademark = by_record.get(f"DEMO-{index:04d}")
        if trademark:
            trademark.image_asset_id = asset.id
            image_vector = runtime.embed_image(full_path)
            if image_vector is not None:
                existing = session.scalar(
                    select(TrademarkFeature).where(
                        TrademarkFeature.trademark_id == trademark.id,
                        TrademarkFeature.feature_type == "image",
                        TrademarkFeature.model_name == settings.image_embedding_model,
                    )
                )
                if existing is None:
                    session.add(
                        TrademarkFeature(
                            trademark_id=trademark.id,
                            feature_type="image",
                            model_name=settings.image_embedding_model,
                            dimension=int(image_vector.size),
                            preprocess_version="rgb-exif-stripped-v1",
                            vector_blob=vector_to_blob(image_vector),
                        )
                    )
    session.commit()


def seed_cz_visual_showcase(session: Session) -> None:
    """Create an operator-owned, clearly labelled visual-similarity exhibit.

    One candidate (SWISSCOAT) is an auditable record from the IPO CZ ST.96
    release.  The companion assets are generated course samples, never presented
    as official Czech trademark artwork.  Their declared score gradient exists
    only for the dedicated case below so a live presentation can demonstrate
    high-to-low visual comparison predictably.
    """
    settings = get_settings()
    admin = session.scalar(select(User).where(User.email == settings.demo_admin_email.lower()))
    demo_source = session.scalar(select(SourceDefinition).where(SourceDefinition.source_key == "demo-json"))
    if admin is None or demo_source is None:
        return
    project = session.scalar(
        select(Project).where(
            Project.owner_id == admin.id,
            Project.name == "捷克真实数据 · 图样相似度梯度演示",
        )
    )
    if project is None:
        project = Project(
            owner_id=admin.id,
            name="捷克真实数据 · 图样相似度梯度演示",
            business_description=(
                "用于课程汇报：以捷克工业产权局 IPO CZ 公开记录 SWISSCOAT（CZ-112187）为真实来源，"
                "配合明确标识的 AI 生成对照图样，展示图文、多模态检索和风险报告中的相似度梯度。"
            ),
            status="active",
        )
        session.add(project)
        session.flush()

    asset_specs = {
        "official": ("cz-swisscoat-official.png", "捷克 IPO CZ 官方公开图样（SWISSCOAT）", False),
        "reference": ("cz-reference-target.png", "课程图样梯度基准（AI 生成）", True),
        "high": ("cz-high-similarity.png", "课程对照图样：高相似（AI 生成）", True),
        "low": ("cz-low-similarity.png", "课程对照图样：较低相似（AI 生成）", True),
        "very_low": ("cz-very-low-similarity.png", "课程对照图样：很低相似（AI 生成）", True),
    }
    asset_dir = Path(__file__).with_name("demo_assets")
    assets: dict[str, ImageAsset] = {}
    for key, (filename, label, is_demo) in asset_specs.items():
        content = (asset_dir / filename).read_bytes()
        processed = process_image(content, filename, settings)
        asset = session.scalar(select(ImageAsset).where(ImageAsset.sha256 == processed.sha256))
        storage_key = f"course-showcase/{filename}"
        target_path = settings.upload_dir / storage_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not target_path.exists():
            target_path.write_bytes(processed.content)
        if asset is None:
            asset = ImageAsset(
                owner_id=admin.id,
                project_id=project.id,
                storage_key=storage_key,
                original_filename=label,
                mime_type=processed.mime_type,
                sha256=processed.sha256,
                byte_size=len(processed.content),
                width=processed.width,
                height=processed.height,
                ocr_text=None,
                ocr_confidence=None,
                ocr_model="source-file" if not is_demo else "openai-imagegen-course-sample",
                phash=processed.phash,
                is_demo=is_demo,
            )
            session.add(asset)
            session.flush()
        else:
            asset.owner_id = admin.id
            asset.project_id = project.id
        assets[key] = asset

    # Attach the actual archived image only to its matching official record.
    official = session.scalar(
        select(Trademark).where(Trademark.source_record_id == "CZ-TM-112187")
    )
    if official is not None:
        official.image_asset_id = assets["official"].id

    showcase_group = "cz-swisscoat-visual-gradient-v1"
    candidates = [
        (
            "CZ-SHOWCASE-HIGH-001",
            "SWISSCOAT+",
            [9],
            "课程对照样本",
            "high",
            0.94,
            "与基准构图近似：同为同心环、顶部星芒与右侧射线的组合。",
        ),
        (
            "CZ-SHOWCASE-LOW-001",
            "CRESCENTA",
            [9],
            "课程对照样本",
            "low",
            0.41,
            "保留抽象几何语言，但主体结构已改为新月、六边形和圆点。",
        ),
        (
            "CZ-SHOWCASE-VERYLOW-001",
            "TERRA RISE",
            [25],
            "课程对照样本",
            "very_low",
            0.08,
            "三角山形与暖色体系，构图、色彩和类别均与基准差异明显。",
        ),
    ]
    for record_id, name, classes, applicant, asset_key, score, rationale in candidates:
        item = session.scalar(
            select(Trademark).where(
                Trademark.source_id == demo_source.id,
                Trademark.source_record_id == record_id,
            )
        )
        raw = {
            "jurisdiction": "DEMO",
            "visual_showcase": {
                "group": showcase_group,
                "score": score,
                "basis": "课程展示预设梯度；仅用于演示多模态评分可视化",
                "rationale": rationale,
            },
            "asset_provenance": "OpenAI ImageGen 课程样本，2026-07-25 生成",
        }
        if item is None:
            item = Trademark(
                source_id=demo_source.id,
                source_record_id=record_id,
                raw_record_hash=hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest(),
                name=name,
                normalized_name=name.casefold(),
                application_number=f"ML-{record_id[-8:]}",
                applicant=applicant,
                nice_classes=classes,
                goods_services=["课程展示用图样相似度检索样本"],
                status="课程展示样本",
                status_date=date(2026, 7, 25),
                application_date=date(2026, 7, 25),
                source_url="demo://marklens/course-showcase/cz-visual-gradient",
                image_asset_id=assets[asset_key].id,
                is_demo=True,
                raw_record=raw,
            )
            session.add(item)
        else:
            item.image_asset_id = assets[asset_key].id
            item.raw_record = raw
            item.nice_classes = classes
        session.flush()

    case_specs = [
        (
            "cz-official-swisscoat",
            "SWISSCOAT（CZ-112187 真实记录）",
            "捷克 IPO CZ 公开商标记录，用于展示真实来源、图样归档与检索溯源。",
            [9],
            "official",
        ),
        (
            "cz-gradient-reference",
            "SWISSCOAT 图样相似度基准",
            "AI 生成的课程基准图样；检索报告会以透明标识的展示梯度呈现高、较低与很低的图样相似度。",
            [9],
            "reference",
        ),
        ("cz-gradient-high", "SWISSCOAT+（高相似对照）", "AI 生成的高相似课程对照图样。", [9], "high"),
        ("cz-gradient-low", "CRESCENTA（较低相似对照）", "AI 生成的较低相似课程对照图样。", [9], "low"),
        ("cz-gradient-very-low", "TERRA RISE（很低相似对照）", "AI 生成的很低相似课程对照图样。", [25], "very_low"),
    ]
    for scenario, name, description, classes, asset_key in case_specs:
        exists = session.scalar(
            select(CaseRecord).where(
                CaseRecord.project_id == project.id,
                CaseRecord.facts_snapshot["showcase_scenario"].as_string() == scenario,
            )
        )
        if exists is None:
            session.add(
                CaseRecord(
                    owner_id=admin.id,
                    project_id=project.id,
                    trademark_name=name,
                    business_description=description,
                    nice_classes=classes,
                    image_asset_id=assets[asset_key].id,
                    facts_snapshot={
                        "showcase_scenario": scenario,
                        "visual_showcase_group": showcase_group if scenario == "cz-gradient-reference" else None,
                        "asset_provenance": "IPO CZ official archive" if asset_key == "official" else "OpenAI ImageGen course sample",
                    },
                )
            )
    session.commit()


def seed_text_features(session: Session) -> None:
    settings = get_settings()
    runtime = LocalModelRuntime(settings)
    trademarks = list(session.scalars(select(Trademark)).all())
    vectors = runtime.embed_texts([item.name for item in trademarks])
    for trademark, vector in zip(trademarks, vectors, strict=True):
        existing = session.scalar(
            select(TrademarkFeature).where(
                TrademarkFeature.trademark_id == trademark.id,
                TrademarkFeature.feature_type == "text",
                TrademarkFeature.model_name == settings.text_embedding_model,
            )
        )
        if existing is None:
            session.add(
                TrademarkFeature(
                    trademark_id=trademark.id,
                    feature_type="text",
                    model_name=settings.text_embedding_model,
                    dimension=int(vector.size),
                    preprocess_version="nfkc-v1",
                    vector_blob=vector_to_blob(vector),
                )
            )
    session.commit()


def seed_legal_sources(session: Session) -> None:
    settings = get_settings()
    runtime = LocalModelRuntime(settings)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=120,
        separators=["\n第", "\n一、", "\n（一）", "。", "；", "，", ""],
    )
    for seed in LAW_SEEDS:
        source = session.scalar(
            select(LegalSource).where(LegalSource.source_url == seed["source_url"])
        )
        content = "\n".join(f"{locator}\n{text}" for locator, text in seed["sections"])
        verification_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if source is None:
            source = LegalSource(
                title=seed["title"],
                authority=seed["authority"],
                source_url=seed["source_url"],
                source_type=seed["source_type"],
                jurisdiction="CN",
                version_label=seed["version_label"],
                effective_from=seed["effective_from"],
                effective_to=seed["effective_to"],
                verification_hash=verification_hash,
                is_official=True,
            )
            session.add(source)
            session.flush()
        for locator, text in seed["sections"]:
            parts = splitter.split_text(text)
            vectors = runtime.embed_texts(parts)
            for offset, (part, vector) in enumerate(zip(parts, vectors, strict=True), start=1):
                part_locator = locator if len(parts) == 1 else f"{locator} 第{offset}段"
                text_hash = hashlib.sha256(part.encode("utf-8")).hexdigest()
                existing = session.scalar(
                    select(LegalChunk).where(
                        LegalChunk.legal_source_id == source.id,
                        LegalChunk.text_hash == text_hash,
                    )
                )
                if existing is None:
                    session.add(
                        LegalChunk(
                            legal_source_id=source.id,
                            title=f"{seed['title']} - {part_locator}",
                            locator=part_locator,
                            text=part,
                            text_hash=text_hash,
                            embedding_blob=vector_to_blob(vector),
                            embedding_model=settings.text_embedding_model,
                            embedding_dimension=int(vector.size),
                            preprocess_version="legal-split-900-120-v1",
                        )
                    )
    session.commit()


def seed_product_content(session: Session) -> None:
    """Create a small, clearly labelled teaching product experience."""
    settings = get_settings()
    admin = session.scalar(select(User).where(User.email == settings.demo_admin_email.lower()))
    if admin is None:
        admin = User(
            email=settings.demo_admin_email.lower(),
            password_hash=hash_password(settings.demo_admin_password),
            display_name="MarkLens 演示运营员",
        )
        session.add(admin)
        session.flush()
    for role in ("user", "operator", "admin"):
        if (
            session.scalar(
                select(UserRole).where(UserRole.user_id == admin.id, UserRole.role == role)
            )
            is None
        ):
            session.add(UserRole(user_id=admin.id, role=role))
    topics = [
        ("trademark-basics", "商标从哪里开始", "认识商标、显著性和注册保护的边界。", 1),
        ("similarity", "如何理解商标近似", "从音、形、义与商品服务关系理解近似判断。", 2),
        ("application-path", "注册流程与维护", "从申请到续展，理解每个阶段要做的事。", 3),
    ]
    for slug, title, summary, order_index in topics:
        topic = session.scalar(select(LearningTopic).where(LearningTopic.slug == slug))
        if topic is None:
            topic = LearningTopic(
                slug=slug, title=title, summary=summary, order_index=order_index, is_published=True
            )
            session.add(topic)
            session.flush()
        existing_titles = set(
            session.scalars(
                select(LearningArticle.title).where(LearningArticle.topic_id == topic.id)
            ).all()
        )
        for item_index, (article_title, body) in enumerate(_learning_items(slug), start=1):
            if article_title not in existing_titles:
                session.add(
                    LearningArticle(
                        topic_id=topic.id,
                        title=article_title,
                        body=body,
                        citations=[],
                        order_index=item_index,
                        is_published=True,
                    )
                )
    video_items = [
        (
            "trademark-basics",
            "商标知识小课堂：先查一查名称是否已被申请",
            "bilibili",
            "https://www.bilibili.com/video/BV1Hy4y157ra",
            "外部短课",
            "理解命名前先做在先申请检索的必要性，并知道该用什么问题开始核查。",
        ),
        (
            "trademark-basics",
            "公开课：商标的注册",
            "bilibili",
            "https://www.bilibili.com/video/BV1Nd4y147wj/",
            "公开课节选",
            "建立商标注册制度和申请条件的整体框架。",
        ),
        (
            "similarity",
            "商标实务运用：近似与混淆的判断视角",
            "bilibili",
            "https://www.bilibili.com/video/BV1gv411q77G/",
            "外部讲座",
            "把名称、图样、商品服务关系放在同一个近似判断框架中理解。",
        ),
        (
            "application-path",
            "如何办理商标申请：动画科普",
            "bilibili",
            "https://www.bilibili.com/video/BV1Ag411e7zg/",
            "外部短课",
            "了解提交商标申请前需要准备的基本材料和流程节点。",
        ),
        (
            "application-path",
            "谁可以申请商标？注册需要哪些材料？",
            "bilibili",
            "https://www.bilibili.com/video/BV18142167VR/",
            "外部短课",
            "梳理申请主体、材料准备与图样要求等基础问题。",
        ),
    ]
    for order_index, (topic_slug, title, provider, url, duration, objective) in enumerate(
        video_items, start=1
    ):
        topic = session.scalar(select(LearningTopic).where(LearningTopic.slug == topic_slug))
        if topic and session.scalar(select(LearningVideo).where(LearningVideo.external_url == url)) is None:
            session.add(
                LearningVideo(
                    topic_id=topic.id,
                    title=title,
                    provider=provider,
                    external_url=url,
                    duration_label=duration,
                    learning_objective=objective,
                    order_index=order_index,
                    is_published=True,
                )
            )
    if (
        session.scalar(
            select(PracticeQuestion).where(PracticeQuestion.title == "相似商标的判断重点")
        )
        is None
    ):
        session.add(
            PracticeQuestion(
                title="相似商标的判断重点",
                prompt="判断两个文字商标是否近似时，以下哪一种做法更符合基本判断思路？",
                options=[
                    {"id": "a", "label": "只比较是否有完全相同的文字"},
                    {"id": "b", "label": "综合比较音、形、义、整体印象及商品服务关系"},
                    {"id": "c", "label": "只看双方是否属于同一个尼斯类别"},
                ],
                correct_option="b",
                explanation="近似判断应结合商标标志本身的音、形、义、整体表现形式和商品服务类似关系综合分析。",
                difficulty="basic",
                is_published=True,
            )
        )
    existing_questions = set(session.scalars(select(PracticeQuestion.title)).all())
    for item in _practice_items():
        if str(item["title"]) not in existing_questions:
            session.add(
                PracticeQuestion(
                    title=str(item["title"]),
                    prompt=str(item["prompt"]),
                    options=item["options"],
                    correct_option=str(item["correct_option"]),
                    explanation=str(item["explanation"]),
                    difficulty=str(item["difficulty"]),
                    is_published=True,
                )
            )
    session.commit()


def assign_legacy_demo_records(session: Session) -> None:
    """Place pre-product records in one explicit operator-owned demo project."""
    settings = get_settings()
    owner = session.scalar(select(User).where(User.email == settings.demo_admin_email.lower()))
    if owner is None:
        return
    project = session.scalar(
        select(Project).where(Project.owner_id == owner.id, Project.name == "历史演示归档")
    )
    if project is None:
        project = Project(
            owner_id=owner.id,
            name="历史演示归档",
            business_description="产品化迁移前生成的教学案例与分析记录。",
            status="archived",
        )
        session.add(project)
        session.flush()
    cases = session.scalars(select(CaseRecord).where(CaseRecord.owner_id.is_(None))).all()
    for case in cases:
        case.owner_id = owner.id
        case.project_id = project.id
        if case.image_asset_id:
            asset = session.get(ImageAsset, case.image_asset_id)
            if asset and asset.owner_id is None:
                asset.owner_id = owner.id
                asset.project_id = project.id
    for search in session.scalars(
        select(SearchRecord).where(SearchRecord.owner_id.is_(None))
    ).all():
        search.owner_id = owner.id
    for analysis in session.scalars(
        select(RiskAnalysis).where(RiskAnalysis.owner_id.is_(None))
    ).all():
        analysis.owner_id = owner.id
    for document in session.scalars(
        select(DocumentDraft).where(DocumentDraft.owner_id.is_(None))
    ).all():
        document.owner_id = owner.id
    for consultation in session.scalars(
        select(Consultation).where(Consultation.owner_id.is_(None))
    ).all():
        consultation.owner_id = owner.id
    for run in session.scalars(select(AgentRun).where(AgentRun.owner_id.is_(None))).all():
        run.owner_id = owner.id
        run.visibility = "ops" if run.agent_type == "ingestion" else "user"
    session.commit()


def seed_all(session: Session) -> None:
    prepare_demo_files()
    ensure_source_definitions(session)
    sync_source(session, "demo-json", page_size=20)
    seed_demo_assets(session)
    seed_legal_sources(session)
    seed_product_content(session)
    seed_cz_visual_showcase(session)
    seed_text_features(session)
    assign_legacy_demo_records(session)


def main() -> None:
    with get_session_factory()() as session:
        seed_all(session)
    print("MarkLens seed completed: 60 demo trademarks, 12 demo logos, legal evidence.")


if __name__ == "__main__":
    main()
