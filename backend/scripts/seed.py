"""Seed the catalog with categories and products.

Run from backend/:  python -m scripts.seed

Idempotent: existing rows are matched by slug and left alone, so re-running
tops up rather than duplicating.
"""

import asyncio
import re
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Category, Product

CATEGORIES = [
    ("Accessories", "Scarves, belts, hats and small leather goods."),
    ("Shirts", "Casual and formal tops in cotton, linen and merino."),
    ("Footwear", "Boots, sneakers and loafers for every season."),
    ("Bags", "Totes, backpacks and travel luggage."),
    ("Outerwear", "Coats and jackets built for weather."),
]

# (category name, product name, price, stock)
PRODUCTS = [
    ("Accessories", "Wool Scarf", "29.99", 40),
    ("Accessories", "Leather Belt", "45.00", 25),
    ("Accessories", "Silk Tie", "39.50", 30),
    ("Accessories", "Knit Beanie", "22.00", 60),
    ("Accessories", "Cashmere Gloves", "68.00", 15),
    ("Accessories", "Canvas Cap", "24.99", 55),
    ("Accessories", "Linen Pocket Square", "16.00", 70),
    ("Accessories", "Merino Wool Socks", "14.50", 120),
    ("Accessories", "Tortoise Sunglasses", "89.00", 18),
    ("Accessories", "Bifold Leather Wallet", "55.00", 35),
    ("Shirts", "Linen Shirt", "59.00", 40),
    ("Shirts", "Oxford Button-Down", "65.00", 45),
    ("Shirts", "Flannel Overshirt", "72.00", 20),
    ("Shirts", "Denim Western Shirt", "68.00", 22),
    ("Shirts", "Poplin Dress Shirt", "62.00", 38),
    ("Shirts", "Chambray Shirt", "58.00", 30),
    ("Shirts", "Heavyweight Cotton Tee", "28.00", 90),
    ("Shirts", "Merino Polo", "78.00", 25),
    ("Shirts", "Waffle Henley", "44.00", 33),
    ("Shirts", "Silk Blouse", "95.00", 12),
    ("Footwear", "Leather Chelsea Boots", "189.00", 14),
    ("Footwear", "Suede Loafers", "155.00", 16),
    ("Footwear", "Canvas Sneakers", "69.00", 50),
    ("Footwear", "Trail Running Shoes", "125.00", 28),
    ("Footwear", "Derby Shoes", "165.00", 12),
    ("Footwear", "Espadrilles", "48.00", 42),
    ("Footwear", "Waterproof Hiking Boots", "210.00", 9),
    ("Footwear", "Slip-On Sneakers", "72.00", 36),
    ("Footwear", "Leather Sandals", "85.00", 24),
    ("Footwear", "Wool Slippers", "52.00", 30),
    ("Bags", "Leather Tote", "220.00", 10),
    ("Bags", "Canvas Backpack", "98.00", 32),
    ("Bags", "Weekend Duffel", "175.00", 14),
    ("Bags", "Messenger Bag", "140.00", 18),
    ("Bags", "Belt Bag", "62.00", 45),
    ("Bags", "Laptop Sleeve", "45.00", 60),
    ("Bags", "Drawstring Pouch", "28.00", 75),
    ("Bags", "Travel Holdall", "245.00", 7),
    ("Bags", "Crossbody Bag", "115.00", 26),
    ("Bags", "Camera Bag", "132.00", 11),
    ("Outerwear", "Wool Overcoat", "395.00", 8),
    ("Outerwear", "Quilted Jacket", "185.00", 20),
    ("Outerwear", "Denim Jacket", "110.00", 34),
    ("Outerwear", "Cotton Trench Coat", "310.00", 9),
    ("Outerwear", "Down Puffer Jacket", "265.00", 15),
    ("Outerwear", "Bomber Jacket", "148.00", 22),
    ("Outerwear", "Packable Rain Shell", "132.00", 27),
    ("Outerwear", "Waxed Field Jacket", "289.00", 11),
    ("Outerwear", "Wool Peacoat", "340.00", 6),
    ("Outerwear", "Insulated Gilet", "125.00", 29),
]


def slugify(text: str) -> str:
    """'Wool Scarf' -> 'wool-scarf'."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


async def seed() -> None:
    async with SessionLocal() as session:
        # Match on slug so re-runs insert only what is missing.
        existing_categories = {
            c.slug: c for c in (await session.scalars(select(Category))).all()
        }
        existing_products = set((await session.scalars(select(Product.slug))).all())

        new_categories = 0
        for name, description in CATEGORIES:
            slug = slugify(name)
            if slug in existing_categories:
                continue
            category = Category(name=name, slug=slug, description=description)
            session.add(category)
            existing_categories[slug] = category
            new_categories += 1

        # Assigns the generated ids, which the products below need. Still
        # inside the transaction -- nothing is permanent until commit().
        await session.flush()

        new_products = 0
        for category_name, name, price, stock in PRODUCTS:
            slug = slugify(name)
            if slug in existing_products:
                continue
            session.add(
                Product(
                    name=name,
                    slug=slug,
                    description=f"{name} from our {category_name.lower()} range.",
                    # Decimal("29.99"), never Decimal(29.99): a float argument
                    # has already lost precision before Decimal sees it.
                    price=Decimal(price),
                    stock=stock,
                    is_active=True,
                    # Assigning the relationship lets SQLAlchemy fill in
                    # category_id itself.
                    category=existing_categories[slugify(category_name)],
                )
            )
            new_products += 1

        await session.commit()

    print(f"categories: +{new_categories} new")
    print(f"products  : +{new_products} new")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
