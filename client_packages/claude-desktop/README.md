# Claude for Frappe ERP - Desktop Extension

[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/paborana/pibiassistant)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#compatibility)
[![Claude Desktop](https://img.shields.io/badge/Claude%20Desktop-MCP%20Extension-purple.svg)](https://claude.ai/desktop)
[![Frappe](https://img.shields.io/badge/Frappe-ERP%20Bridge-orange.svg)](https://frappe.io)

A **Claude Desktop Extension** that connects your **Claude Desktop** application to **Frappe ERP systems** via the **pibiAssistant** app. This extension package provides an intelligent MCP (Model Context Protocol) server for AI-powered business data analysis and document management.

> **Part of the [pibiAssistant](https://github.com/paborana/pibiassistant) project** - This is the client-side extension that connects to the server-side Frappe app.

## 🌟 Features

### 📊 **Data Analysis & Visualization**
- **Execute Python Code** - Run custom Python scripts with full Frappe framework access
- **Statistical Analysis** - Comprehensive analysis of business data with trends and correlations
- **Interactive Visualizations** - Create bar charts, line graphs, pie charts, and heatmaps
- **Custom SQL Queries** - Execute complex database queries for business intelligence

### 📋 **Document Management**
- **CRUD Operations** - Create, read, update, and delete Frappe documents
- **Smart Search** - Global and DocType-specific search with natural language
- **Document Listing** - Browse and filter documents with advanced criteria
- **Link Field Search** - Find related documents and reference data

### 📈 **Reporting & Analytics**
- **Report Execution** - Run financial, sales, inventory, and custom reports
- **Report Discovery** - Browse available reports across all modules
- **Report Analysis** - Get detailed column information and data structure
- **Business Intelligence** - Generate insights from your ERP data

### 🔧 **System Management**
- **Metadata Access** - Explore DocType structures, fields, and relationships
- **Permission Management** - Check user permissions and access rights
- **Workflow Management** - Handle document approval processes
- **API Integration** - Secure connection to any Frappe/ERPNext instance

## 🚀 Quick Start

### Prerequisites

- **Claude Desktop** installed and running
- **Frappe/ERPNext instance** with API access enabled
- **[pibiAssistant app](https://github.com/paborana/pibiassistant)** installed on your Frappe server
- **Python 3.8+** available on your system

> **Important**: You must install the pibiAssistant app on your Frappe server first. This extension connects to that app.

### Installation

#### Step 1: Install pibiAssistant App

First, install the server-side app on your Frappe instance:

```bash
# On your Frappe server
bench get-app pibiassistant https://github.com/paborana/pibiassistant
bench install-app pibiassistant
bench restart
```

#### Step 2: Install Claude Desktop Extension

**Option A: Direct Download (Recommended)**

1. Download the latest `claude-for-frappe-v1.2.0.dxt` from the [main project releases](https://github.com/paborana/pibiassistant/releases)
2. Double-click the `.dxt` file to install in Claude Desktop
3. Configure your Frappe server connection (see [Configuration](#configuration))

**Option B: Manual Build from Source**

```bash
# Clone the main repository
git clone https://github.com/paborana/pibiassistant.git
cd pibiassistant/client_packages/claude-desktop

# Install dependencies
pip install -r requirements.txt

# Create DXT package (see CONTRIBUTING.md for details)
```

## ⚙️ Configuration

After installation, you'll need to configure your Frappe server connection:

### 1. Get Frappe API Credentials

In your Frappe/ERPNext instance:
1. Go to **Settings** → **API** → **Generate API Key**
2. Create a new API Key and Secret for your user
3. Note down the **API Key** and **API Secret**

### 2. Configure Claude Desktop Extension

1. Open Claude Desktop Settings
2. Find "Claude for Frappe ERP" in your extensions
3. Fill in the configuration:

```json
{
  "server_url": "https://your-frappe-instance.com",
  "api_key": "your_api_key_here",
  "api_secret": "your_api_secret_here",
  "debug_mode": "0"
}
```

### 3. Test Connection

Start a new conversation in Claude Desktop and try:

```
List all customers in my ERP system
```

## 📖 Usage Examples

### Data Analysis
```
Analyze sales data for the last quarter and show me trends by customer segment
```

### Document Management
```
Create a new customer named "Acme Corp" with email contact@acme.com
```

### Reporting
```
Run the "Sales Invoice Report" for this month and summarize the findings
```

### Visualization
```
Create a bar chart showing top 10 products by sales revenue
```

### System Exploration
```
What fields are available in the Item DocType?
```

## 🖼️ Screenshots

*Screenshots coming soon - this section will be updated in the next release*

## 🔒 Security & Privacy

- **Your Data Stays Local** - All data remains on your Frappe server
- **Secure Authentication** - Uses Frappe's built-in API key system
- **No Data Collection** - No data is sent to third parties
- **Encrypted Communication** - HTTPS required for all connections
- **Permission Respect** - Only accesses data you have permission to view

## 🛠️ Development

This extension is part of the larger pibiAssistant project. For development:

- **[BUILD.md](BUILD.md)** - Complete guide to building DXT packages and validating manifests
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development setup and guidelines for this extension
- **[Official Extension Docs](https://www.anthropic.com/engineering/desktop-extensions)** - Anthropic's desktop extension documentation
- **Core App Development**: See the [main project](https://github.com/paborana/pibiassistant) for server-side development
- **Tool Development**: See [Tool Development Guide](https://github.com/paborana/pibiassistant/blob/main/docs/PLUGIN_DEVELOPMENT.md)

## 📋 Requirements

### Frappe Server Requirements
- Frappe Framework v13+ or ERPNext v13+
- pibiAssistant app installed
- API access enabled
- HTTPS connection (recommended)

### System Requirements
- Python 3.8+
- Claude Desktop application
- Internet connection to your Frappe server

## 🆘 Troubleshooting

### Connection Issues
- Verify your API credentials are correct
- Ensure your Frappe server is accessible
- Check that pibiAssistant app is installed and enabled

### Permission Errors
- Verify your user has appropriate permissions in Frappe
- Check that API access is enabled for your user role

### Debug Mode
Enable debug mode in the extension configuration to get detailed logs:
```json
{
  "debug_mode": "1"
}
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Frappe Framework](https://frappe.io) for the amazing ERP platform
- [Anthropic](https://anthropic.com) for Claude Desktop and MCP protocol
- The open-source community for inspiration and support

## 📞 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/paborana/pibiassistant/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/paborana/pibiassistant/discussions)
- 📖 **Documentation**: [pibiAssistant Docs](https://github.com/paborana/pibiassistant/blob/main/docs/)
- 📧 **Email**: jypaulclinton@gmail.com

### Related Documentation

- **[pibiAssistant](https://github.com/paborana/pibiassistant)** - Main project repository
- **[Installation Guide](https://github.com/paborana/pibiassistant/blob/main/docs/README.md)** - Complete setup instructions
- **[API Reference](https://github.com/paborana/pibiassistant/blob/main/docs/API_REFERENCE.md)** - Technical documentation
- **[Tool Usage Guide](https://github.com/paborana/pibiassistant/blob/main/docs/TOOL_USAGE_GUIDE.md)** - How to use all 21 tools
- **[Claude Desktop Extensions](https://www.anthropic.com/engineering/desktop-extensions)** - Official Anthropic documentation
- **[MCP Protocol](https://modelcontextprotocol.io)** - Model Context Protocol specification

---

**Transform your business data analysis with AI** - Start using Claude for Frappe ERP today! 🚀

---

*This Claude Desktop Extension is part of the [pibiAssistant](https://github.com/paborana/pibiassistant) project.*

*Location: `client_packages/claude-desktop/` - See [Client Packages](../README.md) for other AI platform integrations.*