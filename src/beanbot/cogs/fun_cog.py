from __future__ import annotations

import random
import re

import discord
from discord.ext import commands

from beanbot.discord.bot import BeanBot

_DICE_PATTERN = re.compile(r"^(?:(\d{1,2})d)?(\d{1,3})$")


def _safe_allowed_mentions() -> discord.AllowedMentions:
    return discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=False)


def _parse_dice(raw: str) -> tuple[int, int] | None:
    match = _DICE_PATTERN.match(raw.replace(" ", ""))
    if not match:
        return None

    dice_count = int(match.group(1) or 1)
    sides = int(match.group(2))

    if dice_count < 1 or dice_count > 20:
        return None
    if sides < 2 or sides > 1000:
        return None

    return dice_count, sides


class FunCog(commands.Cog, name="Fun Commands"):
    def __init__(self, bot: BeanBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="coinflip", description="Flip a coin")
    @commands.bot_has_permissions(send_messages=True)
    async def coinflip(self, ctx: commands.Context) -> None:
        result = random.choice(["Heads", "Tails"])
        await ctx.reply(f"{result}!", allowed_mentions=_safe_allowed_mentions())

    @commands.hybrid_command(name="roll", description="Roll dice (default: 1d6)")
    @commands.bot_has_permissions(send_messages=True)
    async def roll(self, ctx: commands.Context, *, dice: str | None = None) -> None:
        dice_raw = (dice or "1d6").strip().lower()
        parsed = _parse_dice(dice_raw)
        if not parsed:
            await ctx.reply(
                "Use the format `NdM` (example: 2d20).", allowed_mentions=_safe_allowed_mentions()
            )
            return

        dice_count, sides = parsed
        rolls = [random.randint(1, sides) for _ in range(dice_count)]
        total = sum(rolls)
        rolls_display = ", ".join(str(roll) for roll in rolls)

        await ctx.reply(
            f"You rolled {dice_count}d{sides}: {rolls_display} (total {total}).",
            allowed_mentions=_safe_allowed_mentions(),
        )

    @commands.hybrid_command(name="choose", description="Choose between comma-separated options")
    @commands.bot_has_permissions(send_messages=True)
    async def choose(self, ctx: commands.Context, *, options: str) -> None:
        choices = [choice.strip() for choice in options.split(",") if choice.strip()]
        if len(choices) < 2:
            await ctx.reply(
                "Give me at least two comma-separated options.",
                allowed_mentions=_safe_allowed_mentions(),
            )
            return

        pick = random.choice(choices)
        await ctx.reply(f"I choose: {pick}", allowed_mentions=_safe_allowed_mentions())

    @commands.hybrid_command(name="rps", description="Play rock, paper, scissors")
    @commands.bot_has_permissions(send_messages=True)
    async def rps(self, ctx: commands.Context, *, choice: str) -> None:
        normalized = choice.strip().lower()
        options = {"rock", "paper", "scissors"}
        if normalized not in options:
            await ctx.reply(
                "Choose one of: rock, paper, or scissors.",
                allowed_mentions=_safe_allowed_mentions(),
            )
            return

        bot_choice = random.choice(sorted(options))

        if normalized == bot_choice:
            outcome = "It's a tie!"
        elif (
            (normalized == "rock" and bot_choice == "scissors")
            or (normalized == "paper" and bot_choice == "rock")
            or (normalized == "scissors" and bot_choice == "paper")
        ):
            outcome = "You win!"
        else:
            outcome = "I win!"

        await ctx.reply(
            f"You chose **{normalized}**. I chose **{bot_choice}**. {outcome}",
            allowed_mentions=_safe_allowed_mentions(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FunCog(bot))
