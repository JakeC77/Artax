"""
test_theo.py - Test script to verify Theo agent prompts and company context injection

Usage:
    python -m app.workflows.theo.test_theo                  # Show all injected prompts
    python -m app.workflows.theo.test_theo --run            # Run a single exchange
    python -m app.workflows.theo.test_theo --run --verbose  # Show full message details
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from app.workflows.theo.theo_agent import (
    create_theo_agent,
    TheoState,
    THEO_PERSONA,
    THEO_INTENT_INSTRUCTIONS,
    COMPANY_CONTEXT,
)
from app.workflows.theo.tools import THEO_TOOLS


def print_section(title: str, content: str, max_lines: int = 0):
    """Print a section with formatting."""
    print("\n" + "=" * 70)
    print(f"📄 {title}")
    print("=" * 70)

    if not content:
        print("(empty - not loaded)")
        return

    lines = content.split('\n')
    if max_lines > 0 and len(lines) > max_lines:
        print('\n'.join(lines[:max_lines]))
        print(f"\n... ({len(lines) - max_lines} more lines)")
    else:
        print(content)


def verify_prompts():
    """Verify all prompts are loaded and show their contents."""
    print("\n" + "#" * 70)
    print("# THEO PROMPT VERIFICATION")
    print("#" * 70)

    # Check module-level constants
    print("\n📋 MODULE-LEVEL PROMPT CONSTANTS:")
    print(f"  • THEO_PERSONA: {len(THEO_PERSONA)} chars" if THEO_PERSONA else "  • THEO_PERSONA: NOT LOADED ❌")
    print(f"  • THEO_INTENT_INSTRUCTIONS: {len(THEO_INTENT_INSTRUCTIONS)} chars" if THEO_INTENT_INSTRUCTIONS else "  • THEO_INTENT_INSTRUCTIONS: NOT LOADED ❌")
    print(f"  • COMPANY_CONTEXT: {len(COMPANY_CONTEXT)} chars ✅" if COMPANY_CONTEXT else "  • COMPANY_CONTEXT: NOT LOADED ⚠️")

    # Show each prompt
    print_section("THEO_PERSONA (always injected)", THEO_PERSONA, max_lines=30)
    print_section("THEO_INTENT_INSTRUCTIONS (intent mode)", THEO_INTENT_INSTRUCTIONS, max_lines=50)
    print_section("COMPANY_CONTEXT (intent mode)", COMPANY_CONTEXT, max_lines=80)

    return bool(COMPANY_CONTEXT)


def verify_agent_instructions():
    """Create agent and verify instruction injection."""
    print("\n" + "#" * 70)
    print("# AGENT INSTRUCTION INJECTION TEST")
    print("#" * 70)

    # Create agent
    agent = create_theo_agent(model="openai:gpt-4o-mini")
    state = TheoState(mode="intent")

    print(f"\n📋 Agent created")
    print(f"📋 State mode: {state.mode}")

    # Check registered instructions
    print(f"\n📋 Registered @agent.instructions functions:")

    instructions = getattr(agent, '_instructions', [])
    if instructions:
        for i, instr_func in enumerate(instructions):
            func_name = getattr(instr_func, '__name__', f'instruction_{i}')
            print(f"  {i+1}. {func_name}")

            # Try to call the function to see what it returns
            try:
                # Create a mock context object
                class MockCtx:
                    pass
                mock_ctx = MockCtx()
                mock_ctx.deps = state  # type: ignore

                # Call the instruction function
                instr_result = instr_func(mock_ctx)  # type: ignore
                if instr_result and isinstance(instr_result, str):
                    preview = instr_result[:100].replace('\n', ' ')
                    print(f"      → Returns {len(instr_result)} chars: \"{preview}...\"")
                else:
                    print(f"      → Returns empty (not active in this mode)")
            except Exception as e:
                print(f"      → Could not preview: {e}")
    else:
        print("  (Could not access _instructions)")

    # Register tools
    for tool_func in THEO_TOOLS.values():
        agent.tool(tool_func)

    print(f"\n📋 Registered tools: {list(THEO_TOOLS.keys())}")

    return agent, state


async def run_single_exchange(agent, state, verbose: bool = False):
    """Run a single exchange to see actual prompts sent to the model."""
    print("\n" + "#" * 70)
    print("# RUNNING SINGLE EXCHANGE (LIVE API CALL)")
    print("#" * 70)

    # Use a domain-specific prompt to see if company context helps
    test_prompt = "I need to analyze our formulary to find drugs where we could save money by switching to generics."

    print(f"\n📨 Test prompt: \"{test_prompt}\"")
    print("\n⏳ Calling API...")

    try:
        result = await agent.run(test_prompt, deps=state)

        print("\n" + "-" * 70)
        print("✅ THEO'S RESPONSE:")
        print("-" * 70)
        print(result.output)

        # Show message structure
        print("\n" + "-" * 70)
        print("📋 MESSAGE HISTORY (what was sent to the model):")
        print("-" * 70)

        all_messages = list(result.all_messages())
        for i, msg in enumerate(all_messages):
            msg_type = type(msg).__name__
            print(f"\n[{i}] {msg_type}")

            # For system/model request messages, show content
            if hasattr(msg, 'parts'):
                for j, part in enumerate(msg.parts):
                    part_type = type(part).__name__
                    if hasattr(part, 'content'):
                        content = str(part.content)
                        if verbose:
                            print(f"    Part[{j}] {part_type}:")
                            print("    " + "-" * 40)
                            for line in content.split('\n'):
                                print(f"    {line}")
                            print("    " + "-" * 40)
                        else:
                            # Show preview
                            if len(content) > 300:
                                print(f"    Part[{j}] {part_type}: {len(content)} chars")
                                # Check for company context markers
                                if "COMPANY/DOMAIN CONTEXT" in content:
                                    print(f"           ✅ Contains COMPANY/DOMAIN CONTEXT section")
                                if "Prescryptive" in content:
                                    print(f"           ✅ Contains 'Prescryptive' mention")
                                if "formulary" in content.lower():
                                    print(f"           ✅ Contains 'formulary' term")
                            else:
                                preview = content[:200].replace('\n', ' ')
                                print(f"    Part[{j}] {part_type}: \"{preview}...\"")
                    elif hasattr(part, 'tool_name'):
                        print(f"    Part[{j}] {part_type}: tool={part.tool_name}")
                    else:
                        print(f"    Part[{j}] {part_type}")

        # Summary
        print("\n" + "-" * 70)
        print("📊 SUMMARY:")
        print("-" * 70)
        print(f"  Total messages: {len(all_messages)}")

        # Check if company context was included
        full_content = str(all_messages)
        if "COMPANY/DOMAIN CONTEXT" in full_content:
            print("  ✅ Company context WAS injected into the prompt")
        else:
            print("  ❌ Company context was NOT found in messages")

        if "Prescryptive" in full_content:
            print("  ✅ 'Prescryptive' appears in the conversation")

        if verbose:
            print("\n💡 Tip: Run without --verbose for a cleaner summary")
        else:
            print("\n💡 Tip: Run with --verbose to see full message contents")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Test Theo agent prompt injection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.workflows.theo.test_theo                  # Verify prompts only
  python -m app.workflows.theo.test_theo --run            # Run live API call
  python -m app.workflows.theo.test_theo --run --verbose  # Show full messages
        """
    )
    parser.add_argument('--run', action='store_true', help='Run a single exchange with live API')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show full message contents')
    args = parser.parse_args()

    # Step 1: Verify prompts are loaded
    has_company_context = verify_prompts()

    if not has_company_context:
        print("\n" + "!" * 70)
        print("⚠️  WARNING: Company context not loaded!")
        print("!" * 70)
        print("\nExpected file: app/workflows/theo/prompts/company_context_phx.txt")
        print("The agent will work but won't have domain-specific context.")

    # Step 2: Verify agent instructions
    agent, state = verify_agent_instructions()

    # Step 3: Optionally run an exchange
    if args.run:
        if not os.getenv("OPENAI_API_KEY") and not os.getenv("AZURE_OPENAI_API_KEY"):
            print("\n❌ No API key found. Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY")
            return 1

        success = await run_single_exchange(agent, state, verbose=args.verbose)
        return 0 if success else 1

    # Done
    print("\n" + "#" * 70)
    print("# VERIFICATION COMPLETE")
    print("#" * 70)

    if has_company_context:
        print("\n✅ All prompts loaded successfully!")
        print("✅ Company context will be injected in intent discovery mode")
    else:
        print("\n⚠️  Prompts loaded but company context is missing")

    print("\n📝 Next steps:")
    print("  • Run with --run to test a live API call")
    print("  • Run with --run --verbose to see full message contents")

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
