"""Idempotent demo dataset and verified legal-source seed command."""

from __future__ import annotations

import hashlib
import json
from datetime import date

from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_session_factory
from .models import ImageAsset, LegalChunk, LegalSource, Trademark, TrademarkFeature
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


def seed_all(session: Session) -> None:
    prepare_demo_files()
    ensure_source_definitions(session)
    sync_source(session, "demo-json", page_size=20)
    seed_demo_assets(session)
    seed_text_features(session)
    seed_legal_sources(session)


def main() -> None:
    with get_session_factory()() as session:
        seed_all(session)
    print("MarkLens seed completed: 60 demo trademarks, 12 demo logos, legal evidence.")


if __name__ == "__main__":
    main()
