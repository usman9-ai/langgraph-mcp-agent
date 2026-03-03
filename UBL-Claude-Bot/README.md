# Claude Desktop Clone

A beautiful web application that replicates the Claude Desktop app's UI/UX using React, TypeScript, and Vite.

## Features

- 🎨 **Pixel-perfect UI** - Matches Claude's clean, modern interface
- 💬 **Chat Interface** - Smooth messaging experience with user and assistant bubbles
- 📝 **Markdown Support** - Full markdown rendering with syntax highlighting
- 🧠 **Thinking Blocks** - Collapsible reasoning steps (MCP-ready)
- 💾 **Conversation History** - Persistent storage of all conversations
- 🎯 **Sidebar Navigation** - Collapsible sidebar for easy conversation management
- ⚡ **Fast & Responsive** - Built with Vite for lightning-fast performance
- 🌙 **Dark Theme** - Beautiful dark mode interface

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type-safe development
- **Vite** - Fast build tool
- **Tailwind CSS** - Utility-first styling
- **Zustand** - State management
- **React Markdown** - Markdown rendering
- **Prism** - Syntax highlighting

## Getting Started

### Prerequisites

- Node.js (v18 or higher)
- npm or yarn

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

This runs the Vite development server with hot module reloading.

### Building

To build the production bundle:

```bash
npm run build
```

Static assets will be emitted to the `dist` folder and can be deployed to any static host.

## Project Structure

```
├── src/
│   ├── components/    # React components
│   │   ├── ChatArea.tsx
│   │   ├── MessageBubble.tsx
│   │   └── Sidebar.tsx
│   ├── store/         # State management
│   │   └── useStore.ts
│   ├── App.tsx        # Main app component
│   ├── main.tsx       # React entry point
│   └── index.css      # Global styles
├── index.html         # HTML template
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## Usage

### Creating a New Chat

Click the "New Chat" button in the sidebar or start typing in the input area.

### Sending Messages

- Type your message in the input box at the bottom
- Press `Enter` to send
- Press `Shift + Enter` for a new line

### Managing Conversations

- Click on any conversation in the sidebar to open it
- Hover over a conversation and click the trash icon to delete it
- Conversations are automatically saved to local storage

### Collapsing Sidebar

Click the arrow icon in the sidebar header to collapse/expand the sidebar for more space.

## Customization

### Changing Colors

Edit the color variables in `src/index.css`:

```css
:root {
  --bg-primary: #003366;
  --bg-secondary: #0A274F;
  --bg-hover: #0F3A73;
  --text-primary: #F2F7FF;
  --text-secondary: #C2DBFF;
  --accent: #8CCBF3;
  --border: #1E4E80;
}
```

### Adding AI Integration

To connect to a real AI backend, modify the `handleSubmit` function in `src/components/ChatArea.tsx`:

```typescript
// Replace the simulated response with your API call
const response = await fetch('YOUR_API_ENDPOINT', {
  method: 'POST',
  body: JSON.stringify({ message: userMessage })
});
```

### Using Thinking Blocks (MCP Integration)

To show reasoning steps in collapsible blocks, format your AI response like this:

```typescript
const responseWithThinking = `[THINKING]${JSON.stringify([
  {
    title: "Analyzing the request",
    content: "Understanding what the user is asking for...",
    status: "complete" // or "thinking" or "error"
  },
  {
    title: "Planning the solution",
    content: "Breaking down the steps needed...",
    status: "complete"
  },
  {
    title: "Generating code",
    content: "Writing the implementation...",
    status: "thinking"
  }
])}[/THINKING]

Your main response content here...
`;

addMessage({ role: 'assistant', content: responseWithThinking });
```

**Status types:**
- `complete` ✅ - Step finished successfully
- `thinking` ⏳ - Step in progress (animated spinner)
- `error` ❌ - Step failed

This is perfect for showing MCP tool execution steps!

## License

MIT

## Acknowledgments

Inspired by the original Claude Desktop application by Anthropic.
