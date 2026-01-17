import discord
from discord.ext import commands
import os
import asyncio
import tempfile
import json
from scorsese.services.kie_client import KIEClient
from scorsese.services.llm_client import LLMClient
from scorsese.approaches.pipeline import PipelineApproach
from scorsese.approaches.agentic import AgenticApproach

class ScorseseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Initialize clients
        api_key = os.getenv("KIE_API_KEY")
        self.kie = KIEClient(api_key=api_key) if api_key else None
        self.llm = LLMClient(model="gpt-4o")
        
        if not self.kie:
             print("Warning: Scorsese Cog initialized without KIE_API_KEY. Video generation will fail.")

    @commands.group(name="scorsese", invoke_without_command=True)
    async def scorsese(self, ctx):
        await ctx.send("Scorsese: AI Viral Video Generator. Use `!scorsese draft` or `!scorsese produce`.")

    @scorsese.command(name="draft")
    async def draft(self, ctx, topic: str, audience: str = "General"):
        """Drafts a script. Usage: !scorsese draft "Topic" "Audience" """
        await ctx.send(f"🎬 **Action!** Drafting script for '{topic}'...")
        
        # Use Pipeline for deterministic drafting in Discord for now (easier to format)
        try:
            pipeline = PipelineApproach(self.llm, self.kie)
            
            # Run blocking call in executor
            script = await asyncio.to_thread(pipeline.draft_script, topic, audience, "Viral Growth")
            
            # Format output
            response = f"**Topic**: {script.topic}\n**Hook**: {script.hook_type}\n\n"
            for seg in script.segments:
                response += f"**{seg.role}** ({seg.duration_estimate}s):\n"
                response += f"🗣️ *Audio*: {seg.audio_text}\n"
                response += f"👁️ *Visual*: {seg.visual_cue.description}\n\n"
            
            # Save to temporary file for "production" later or just attach
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp:
                tmp.write(script.model_dump_json(indent=2))
                tmp_path = tmp.name
                
            file = discord.File(tmp_path, filename=f"script_{topic.split()[0]}.json")
            await ctx.send(f"Here is the draft! Use command to produce: `!scorsese produce <attach_json>`", file=file)
            
        except Exception as e:
            await ctx.send(f"❌ Cut! Error drafting script: {str(e)}")

    @scorsese.command(name="produce")
    async def produce(self, ctx):
        """Produces video from attached JSON script."""
        if not ctx.message.attachments:
            await ctx.send("Please attach a script JSON file.")
            return

        attachment = ctx.message.attachments[0]
        await ctx.send(f"🎥 **Rolling!** Producing videos from {attachment.filename}...")
        
        try:
            # Download attachment
            script_content = await attachment.read()
            from scorsese.models import ViralScript
            script_data = json.loads(script_content)
            script = ViralScript(**script_data)
            
            if not self.kie:
                 await ctx.send("❌ Error: KIE API Key not configured.")
                 return

            # Use Pipeline for production (easier to track progress in POC)
            pipeline = PipelineApproach(self.llm, self.kie)
            
            # Updates messages periodically? For complex bots yes, here just wait/notify
            status_msg = await ctx.send("Sending tasks to KIE.AI...")
            
            final_script = await asyncio.to_thread(pipeline.produce_video, script)
            
            response = "**Production Complete!** 🎞️\n\n"
            for seg in final_script.segments:
                url = seg.video_url or "Checking..."
                response += f"**{seg.role}**: {url}\n"
                
            await ctx.send(response)
            
        except Exception as e:
            await ctx.send(f"❌ Cut! Production error: {str(e)}")

async def setup(bot):
    await bot.add_cog(ScorseseCog(bot))
