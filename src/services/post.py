import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import bleach
import markdown
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.post import Post, PostStatus, PostVisibility
from src.db.models.user import AccessLevel

# Constants
MAX_TITLE_LENGTH = 200
MAX_CONTENT_LENGTH = 100000  # 100KB of text


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def render_markdown(content: str) -> str:
    """Render markdown to HTML and sanitize."""
    html = markdown.markdown(
        content,
        extensions=["fenced_code", "tables", "nl2br"],
    )
    # Sanitize HTML
    allowed_tags = [
        "p", "br", "strong", "em", "u", "s", "code", "pre",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li", "blockquote",
        "a", "img", "table", "thead", "tbody", "tr", "th", "td",
        "figure", "figcaption", "audio", "video", "source",
    ]
    allowed_attrs = {
        "a": ["href", "title"],
        "img": ["src", "alt", "title", "class"],
        "audio": ["controls", "class"],
        "video": ["controls", "class"],
        "source": ["src", "type"],
        "figure": ["class"],
        "figcaption": ["class"],
    }
    return bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs)


def sanitize_inline_html(text: str) -> str:
    """Sanitize inline HTML from Editor.js (allows basic formatting)."""
    allowed_tags = ["b", "i", "u", "s", "a", "code", "mark", "br"]
    allowed_attrs = {"a": ["href"]}
    return bleach.clean(text, tags=allowed_tags, attributes=allowed_attrs, strip=True)


def escape_attr(text: str) -> str:
    """Escape text for use in HTML attributes."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def render_blocks_to_html(blocks_data: dict) -> str:
    """Convert Editor.js blocks to HTML with XSS protection."""
    if not blocks_data or "blocks" not in blocks_data:
        return ""

    html_parts = []
    for block in blocks_data["blocks"]:
        block_type = block.get("type")
        data = block.get("data", {})

        if block_type == "paragraph":
            text = sanitize_inline_html(data.get("text", ""))
            html_parts.append(f"<p>{text}</p>")

        elif block_type == "header":
            level = data.get("level", 2)
            # Ensure level is valid (2-4)
            level = max(2, min(4, int(level)))
            text = sanitize_inline_html(data.get("text", ""))
            html_parts.append(f"<h{level}>{text}</h{level}>")

        elif block_type == "image":
            url = data.get("file", {}).get("url", "")
            # Only allow relative URLs or https URLs
            if url and (url.startswith("/") or url.startswith("https://")):
                url = escape_attr(url)
            else:
                url = ""
            caption = sanitize_inline_html(data.get("caption", ""))
            caption_attr = escape_attr(data.get("caption", ""))
            stretched = "w-full" if data.get("stretched") else "max-w-full"
            caption_html = f'<figcaption class="text-center text-gray-500 mt-2">{caption}</figcaption>' if caption else ""
            html_parts.append(f'''<figure class="my-4">
                <img src="{url}" alt="{caption_attr}" class="{stretched} rounded-lg">
                {caption_html}
            </figure>''')

        elif block_type == "list":
            style = data.get("style", "unordered")
            items = data.get("items", [])
            tag = "ol" if style == "ordered" else "ul"
            list_class = "list-decimal ml-6" if style == "ordered" else "list-disc ml-6"
            items_html = "".join(f"<li>{sanitize_inline_html(item)}</li>" for item in items)
            html_parts.append(f'<{tag} class="{list_class}">{items_html}</{tag}>')

        elif block_type == "quote":
            text = sanitize_inline_html(data.get("text", ""))
            caption = sanitize_inline_html(data.get("caption", ""))
            caption_html = f'<cite class="text-gray-500 text-sm">{caption}</cite>' if caption else ""
            html_parts.append(f'''<blockquote class="border-l-4 border-gray-300 pl-4 italic my-4">
                <p>{text}</p>
                {caption_html}
            </blockquote>''')

        elif block_type == "delimiter":
            html_parts.append('<hr class="my-8 border-gray-200">')

        elif block_type == "code":
            # Code must be fully escaped - no HTML allowed
            code = escape_attr(data.get("code", ""))
            html_parts.append(f'<pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto"><code>{code}</code></pre>')

    return "\n".join(html_parts)


class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_post(
        self,
        title: str,
        content_md: str,
        author_id: UUID,
        visibility: PostVisibility = PostVisibility.PUBLIC,
        status: PostStatus = PostStatus.DRAFT,
        excerpt: Optional[str] = None,
        content_blocks: Optional[dict] = None,
    ) -> Post:
        """Create a new post."""
        # Validate title length
        if len(title) > MAX_TITLE_LENGTH:
            raise ValueError(f"Title exceeds maximum length of {MAX_TITLE_LENGTH}")

        # Validate content length
        if len(content_md) > MAX_CONTENT_LENGTH:
            raise ValueError(f"Content exceeds maximum length of {MAX_CONTENT_LENGTH}")

        # Generate unique slug
        base_slug = slugify(title)
        slug = base_slug
        counter = 1

        while await self.get_by_slug(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Render content to HTML
        if content_blocks:
            content_html = render_blocks_to_html(content_blocks)
        else:
            content_html = render_markdown(content_md)

        # Generate excerpt if not provided
        if not excerpt:
            # Strip HTML and take first 200 chars
            text = re.sub(r"<[^>]+>", "", content_html)
            excerpt = text[:200] + "..." if len(text) > 200 else text

        post = Post(
            author_id=author_id,
            title=title,
            slug=slug,
            content_md=content_md,
            content_html=content_html,
            content_blocks=content_blocks,
            excerpt=excerpt,
            visibility=visibility,
            status=status,
        )

        # Set published_at if publishing immediately
        if status == PostStatus.PUBLISHED:
            post.published_at = datetime.now(timezone.utc)

        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)

        # Update search vector
        await self.update_search_vector(post.id)

        return post

    async def update_search_vector(self, post_id: UUID) -> None:
        """Update full-text search vector for a post."""
        await self.db.execute(
            Post.__table__.update()
            .where(Post.id == post_id)
            .values(
                search_vector=func.to_tsvector(
                    "english",
                    func.coalesce(Post.title, "") + " " + func.coalesce(Post.content_md, ""),
                )
            )
        )
        await self.db.commit()

    async def get_by_slug(self, slug: str) -> Optional[Post]:
        """Get post by slug."""
        result = await self.db.execute(select(Post).where(Post.slug == slug))
        return result.scalar_one_or_none()

    async def get_post_by_slug(
        self, slug: str, user_access_level: AccessLevel = AccessLevel.PUBLIC
    ) -> Optional[Post]:
        """Get post by slug with access level check."""
        visibility_map = {
            AccessLevel.PUBLIC: [PostVisibility.PUBLIC],
            AccessLevel.REGISTERED: [PostVisibility.PUBLIC, PostVisibility.REGISTERED],
            AccessLevel.PREMIUM_1: [
                PostVisibility.PUBLIC,
                PostVisibility.REGISTERED,
                PostVisibility.PREMIUM_1,
            ],
            AccessLevel.PREMIUM_2: [
                PostVisibility.PUBLIC,
                PostVisibility.REGISTERED,
                PostVisibility.PREMIUM_1,
                PostVisibility.PREMIUM_2,
            ],
        }
        allowed = visibility_map.get(user_access_level, [PostVisibility.PUBLIC])

        result = await self.db.execute(
            select(Post).where(
                Post.slug == slug,
                Post.visibility.in_(allowed),
                Post.status == PostStatus.PUBLISHED,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, post_id: UUID) -> Optional[Post]:
        """Get post by ID."""
        result = await self.db.execute(select(Post).where(Post.id == post_id))
        return result.scalar_one_or_none()

    async def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """Get post by ID (string version)."""
        try:
            uuid_id = UUID(post_id)
        except ValueError:
            return None
        return await self.get_by_id(uuid_id)

    async def list_posts(
        self,
        user_access_level: AccessLevel = AccessLevel.PUBLIC,
        page: int = 1,
        per_page: int = 10,
        include_drafts: bool = False,
    ) -> tuple[list[Post], int]:
        """List posts with pagination and access level filtering."""
        # Map access levels to allowed visibilities
        visibility_map = {
            AccessLevel.PUBLIC: [PostVisibility.PUBLIC],
            AccessLevel.REGISTERED: [PostVisibility.PUBLIC, PostVisibility.REGISTERED],
            AccessLevel.PREMIUM_1: [
                PostVisibility.PUBLIC,
                PostVisibility.REGISTERED,
                PostVisibility.PREMIUM_1,
            ],
            AccessLevel.PREMIUM_2: [
                PostVisibility.PUBLIC,
                PostVisibility.REGISTERED,
                PostVisibility.PREMIUM_1,
                PostVisibility.PREMIUM_2,
            ],
        }

        allowed_visibilities = visibility_map.get(
            user_access_level, [PostVisibility.PUBLIC]
        )

        # Build query
        query = select(Post).where(Post.visibility.in_(allowed_visibilities))

        if not include_drafts:
            query = query.where(Post.status == PostStatus.PUBLISHED)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get page - pinned posts first, then by date
        # Use COALESCE so drafts (NULL published_at) sort by created_at
        query = (
            query.order_by(
                Post.is_pinned.desc(),
                Post.pinned_at.desc().nullslast(),
                func.coalesce(Post.published_at, Post.created_at).desc(),
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        result = await self.db.execute(query)
        posts = list(result.scalars().all())

        return posts, total

    async def update_post(
        self,
        post_id,
        title: Optional[str] = None,
        content_md: Optional[str] = None,
        visibility=None,
        status=None,
        excerpt: Optional[str] = None,
        content_blocks: Optional[dict] = None,
        cover_image_id: Optional[UUID] = None,
    ) -> Optional[Post]:
        """Update a post."""
        # Handle string post_id
        if isinstance(post_id, str):
            try:
                post_id = UUID(post_id)
            except ValueError:
                return None

        post = await self.get_by_id(post_id)
        if not post:
            return None

        if title:
            post.title = title

        # Handle content updates
        if content_blocks is not None:
            post.content_blocks = content_blocks
            post.content_html = render_blocks_to_html(content_blocks)
            # Store raw text from blocks for markdown fallback/search
            if content_md:
                post.content_md = content_md
        elif content_md:
            post.content_md = content_md
            post.content_html = render_markdown(content_md)
            post.content_blocks = None  # Clear blocks if using markdown

        if visibility is not None:
            if isinstance(visibility, str):
                post.visibility = PostVisibility(visibility)
            else:
                post.visibility = visibility
        if status is not None:
            if isinstance(status, str):
                post.status = PostStatus(status)
            else:
                post.status = status
            if post.status == PostStatus.PUBLISHED and not post.published_at:
                post.published_at = datetime.now(timezone.utc)
        if excerpt:
            post.excerpt = excerpt

        # Update cover_image_id (can be UUID or None)
        post.cover_image_id = cover_image_id

        await self.db.commit()
        await self.db.refresh(post)

        # Update search vector
        await self.update_search_vector(post.id)

        return post

    async def publish_post(self, post_id: UUID) -> Optional[Post]:
        """Publish a draft post."""
        return await self.update_post(post_id, status="published")

    async def delete_post(self, post_id) -> bool:
        """Delete a post."""
        if isinstance(post_id, str):
            try:
                post_id = UUID(post_id)
            except ValueError:
                return False

        post = await self.get_by_id(post_id)
        if not post:
            return False

        await self.db.delete(post)
        await self.db.commit()
        return True

    async def search_posts(
        self,
        query: str,
        user_access_level: AccessLevel = AccessLevel.PUBLIC,
        page: int = 1,
        per_page: int = 10,
    ) -> tuple[list[Post], int]:
        """Search posts using full-text search."""
        visibility_map = {
            AccessLevel.PUBLIC: [PostVisibility.PUBLIC],
            AccessLevel.REGISTERED: [PostVisibility.PUBLIC, PostVisibility.REGISTERED],
            AccessLevel.PREMIUM_1: [
                PostVisibility.PUBLIC,
                PostVisibility.REGISTERED,
                PostVisibility.PREMIUM_1,
            ],
            AccessLevel.PREMIUM_2: [
                PostVisibility.PUBLIC,
                PostVisibility.REGISTERED,
                PostVisibility.PREMIUM_1,
                PostVisibility.PREMIUM_2,
            ],
        }

        allowed_visibilities = visibility_map.get(
            user_access_level, [PostVisibility.PUBLIC]
        )

        search_query = func.websearch_to_tsquery("english", query)

        base_query = (
            select(Post)
            .where(
                Post.visibility.in_(allowed_visibilities),
                Post.status == PostStatus.PUBLISHED,
                Post.search_vector.op("@@")(search_query),
            )
        )

        # Count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get results
        results_query = (
            base_query.order_by(
                func.ts_rank(Post.search_vector, search_query).desc()
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        result = await self.db.execute(results_query)
        posts = list(result.scalars().all())

        return posts, total

    async def increment_view_count(self, post_id: UUID) -> None:
        """Increment post view count."""
        await self.db.execute(
            Post.__table__.update()
            .where(Post.id == post_id)
            .values(view_count=Post.view_count + 1)
        )
        await self.db.commit()

    async def toggle_pin(self, post_id: UUID) -> Optional[Post]:
        """Toggle pin status of a post."""
        post = await self.get_by_id(post_id)
        if not post:
            return None

        if post.is_pinned:
            post.is_pinned = False
            post.pinned_at = None
        else:
            post.is_pinned = True
            post.pinned_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(post)
        return post
