# Kayara

An AI Japanese tutor that lives inside Anki. It sits in a side panel next to the reviewer, reads the card you're looking at, and writes results into your card fields after you confirm. Think of it as a small coding-agent-style assistant, but for language cards.

## Features

- Chat docked to the right of the reviewer, VS Code agent style
- Card and deck awareness: Kayara sees the current card's fields, notetype, and deck before answering
- One-click save chips: the AI proposes content for a field, you click a chip, Anki asks for confirmation, done
- Field suggestions grounded in your actual notetype. The best candidate gets a star, alternatives get their own chips
- Read-only exploration: the AI can list decks, inspect notetypes, and search notes before it acts
- Batch mode: transform a field across a whole deck or notetype (translate every sentence, fill missing glossaries), with a live progress bar and per-card status
- One-click undo for everything, including entire batch runs
- `/tr` instant command: translate the current sentence and offer to save it
- Model picker with per-model temperature, plus a settings dialog for endpoint, API key, and system prompt
- Works with any OpenAI-compatible endpoint. Built around OmniRoute, but anything that speaks `/v1/chat/completions` will do

## Requirements

- Anki 23.10 or newer (tested on 25.x, Qt6)
- A reachable OpenAI-compatible API endpoint with at least one chat model

## Install

1. Copy the `kayara` folder into your Anki addons directory (`%APPDATA%\Anki2\addons21` on Windows).
2. Copy `config.example.json` to `config.json` in the same folder.
3. Restart Anki.
4. Open the **🌸 Kayara** menu in the menubar, pick **Settings…**, and fill in your endpoint and API key. The **Test koneksi** button verifies everything before you save.

## Usage

- `Ctrl+Alt+K` opens the panel. `Ctrl+Alt+L` opens it with the currently selected text appended.
- Ask in Indonesian or Japanese; Kayara answers in kind.
- Saving works through action blocks the AI emits. Each block becomes a chip under the reply: click it, confirm, and the addon writes to the card. The AI never claims it saved anything; the addon does the saving.
- Batch example: "translate Sentence to Indonesian into SentenceMeaning for all Kiku cards in deck mining". Kayara checks the deck and notetype first, confirms the card count and a preview, then runs with progress. If the result isn't what you wanted, one click on ↶ rolls the whole batch back.

## Configuration

The Settings dialog covers the daily stuff. For manual edits (keybinds, prompt tweaking), see `config.md` or use Anki's built-in addon config. Your `config.json` stays local and is gitignored on purpose.

## Privacy

Cards and chat messages go only to the endpoint you configure. Kayara phones nowhere else.

## License

MIT
