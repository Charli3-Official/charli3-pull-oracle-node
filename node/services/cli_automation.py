"""CLI Automation Services for handling automated command-line interactions."""

import logging
from contextlib import contextmanager
from typing import Any, Callable, List, Optional, Union

import click

logger = logging.getLogger(__name__)


class PromptResponse:
    """Represents a single prompt and its expected response."""

    def __init__(
        self,
        prompt_pattern: Union[str, Callable[[str], bool]],
        response: Any,
        description: str = "",
    ):
        """
        Initialize a prompt response mapping.

        Args:
            prompt_pattern: String pattern to match in prompt text, or callable that takes
                           prompt text and returns True if it matches
            response: The response to return when pattern matches
            description: Optional description for debugging/logging
        """
        self.prompt_pattern = prompt_pattern
        self.response = response
        self.description = description

    def matches(self, prompt_text: str) -> bool:
        """Check if this response matches the given prompt text."""
        if callable(self.prompt_pattern):
            return self.prompt_pattern(prompt_text)
        return self.prompt_pattern.lower() in prompt_text.lower()


class CliAutomationService:
    """Service for automating CLI interactions with configurable responses."""

    def __init__(self, response_sequence: List[PromptResponse]):
        """
        Initialize the CLI automation service.

        Args:
            response_sequence: Ordered list of PromptResponse objects that define
                             how to respond to different prompts
        """
        self.response_sequence = response_sequence
        self.current_index = 0

    def get_next_response(self, prompt_text: str) -> Any:
        """
        Get the next response for a given prompt text.

        Args:
            prompt_text: The text of the prompt being displayed

        Returns:
            The configured response for this prompt
        """
        # Find matching response in sequence
        for i in range(self.current_index, len(self.response_sequence)):
            response = self.response_sequence[i]
            if response.matches(prompt_text):
                self.current_index = i + 1  # Move to next expected prompt
                logger.debug(
                    f"CLI Automation: Matched '{response.description}' -> {response.response}"
                )
                return response.response

        # If no match found, log warning and return a safe default
        logger.warning(
            f"CLI Automation: No matching response found for prompt: {prompt_text}"
        )
        return None

    @contextmanager
    def automate_prompts(self, suppress_output: bool = True):
        """
        Context manager that patches click functions for automated responses.

        Args:
            suppress_output: Whether to suppress click.echo and click.secho output
        """
        original_confirm = click.confirm
        original_prompt = click.prompt
        original_echo = click.echo if suppress_output else None
        original_secho = click.secho if suppress_output else None

        def mock_confirm(text=None, **kwargs):
            response = self.get_next_response(text or "")
            if response is not None:
                return response
            # Default to True for confirm prompts if no specific response
            return True

        def mock_prompt(text=None, **kwargs):
            response = self.get_next_response(text or "")
            if response is not None:
                return response
            # Return default value if available
            return kwargs.get("default")

        def mock_echo(message=None, **kwargs):
            # Suppress echo output
            pass

        def mock_secho(message=None, **kwargs):
            # Suppress secho output
            pass

        try:
            click.confirm = mock_confirm
            click.prompt = mock_prompt
            if suppress_output:
                click.echo = mock_echo
                click.secho = mock_secho
            yield self
        finally:
            click.confirm = original_confirm
            click.prompt = original_prompt
            if suppress_output:
                click.echo = original_echo
                click.secho = original_secho


# Convenience functions for common use cases


def create_node_collect_responses(
    create_collateral: bool = True,
    address_choice: str = "1",
    custom_address: Optional[str] = None,
) -> List[PromptResponse]:
    """
    Create a sequence of responses for NodeCollectBuilder prompts.

    Args:
        create_collateral: Whether to confirm collateral creation
        address_choice: Address selection ("1"=base, "2"=enterprise, "3"=custom)
        custom_address: Custom address if address_choice is "3"

    Returns:
        List of PromptResponse objects for node collect automation
    """
    responses = [
        PromptResponse(
            prompt_pattern=lambda text: "collateral" in text.lower()
            and "utxo" in text.lower(),
            response=create_collateral,
            description="Collateral creation confirmation",
        ),
        PromptResponse(
            prompt_pattern=lambda text: "choice" in text.lower()
            or "enter your choice" in text.lower(),
            response=address_choice,
            description=f"Address choice selection ({address_choice})",
        ),
    ]

    if address_choice == "3" and custom_address:
        responses.append(
            PromptResponse(
                prompt_pattern=lambda text: "address" in text.lower()
                and "enter" in text.lower(),
                response=custom_address,
                description="Custom address input",
            )
        )

    return responses


def create_reward_collection_automation(
    create_collateral: bool = True, reward_destination: str = "base"
) -> CliAutomationService:
    """
    Create a CLI automation service configured for reward collection.

    Args:
        create_collateral: Whether to auto-confirm collateral creation
        reward_destination: "base", "enterprise", or custom address string

    Returns:
        Configured CliAutomationService for reward collection
    """
    # Determine address choice and custom address
    if reward_destination.lower() == "base":
        address_choice = "1"
        custom_address = None
    elif reward_destination.lower() == "enterprise":
        address_choice = "2"
        custom_address = None
    else:
        # Custom address provided
        address_choice = "3"
        custom_address = reward_destination

    responses = create_node_collect_responses(
        create_collateral=create_collateral,
        address_choice=address_choice,
        custom_address=custom_address,
    )

    return CliAutomationService(responses)
