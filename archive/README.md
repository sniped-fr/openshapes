# OpenShapes - Discord Character Bot Platform

## Overview

OpenShapes is an open-source platform for creating and hosting AI character bots on Discord. Based on user feedback and requirements, this implementation plan outlines the development of a feature-rich alternative to commercial character bot services.

## Core Features

### Character Bot

1. **Basic Interaction**

   - Discord.py bot with customizable personality and behavior
   - Message listening with name and mention triggers
   - Slash commands for configuration and information

2. **Advanced Memory System**

   - Long-term memory generation from conversation history
   - Automatic or manual memory updates
   - Persistent memory storage
   - Memory management commands

3. **Lorebook & Knowledge Base**

   - Keyword-triggered lorebook entries
   - General knowledge base for character context
   - Dynamic content inclusion based on conversation
   - Lorebook management interface

4. **Voice Integration**

   - Text-to-speech functionality
   - Voice channel joining/leaving
   - Voice customization options

5. **Social Interaction**
   - Multi-bot support in the same server
   - Conversation history and context

### Management Platform

1. **Web Portal**

   - Discord OAuth integration
   - Character creation and management
   - Bot monitoring and control
   - Credit system management

2. **Bot Manager Service**

   - Centralized management of multiple bot instances
   - Docker containerization for isolation
   - Proxy rotation for avoiding Discord rate limits
   - Automatic health monitoring and recovery

3. **Business Model**
   - Free self-hosted option
   - Tiered pricing for managed hosting

## Development Phases

### Phase 1: Core Bot Framework (2-3 weeks)

- [x] Base Discord.py bot implementation
- [x] Customizable character configuration
- [x] Basic conversation handling
- [ ] Integration with AI APIs (OpenAI, Anthropic)
- [ ] Memory system foundation
- [ ] Lorebook mechanics

### Phase 2: Advanced Features (2-3 weeks)

- [ ] Memory generation and management
- [ ] Lorebook and knowledge base integration
- [ ] Voice support implementation
- [ ] OOC command handling
- [ ] Slash command interface improvements

### Phase 3: Bot Manager (3-4 weeks)

- [x] Bot manager service design
- [ ] Docker integration
- [ ] Proxy rotation implementation
- [ ] Health monitoring and recovery
- [ ] Testing with multiple bot instances

### Phase 4: Web Portal (3-4 weeks)

- [x] FastAPI backend implementation
- [ ] Discord OAuth integration
- [ ] Character creation/management UI
- [ ] User dashboard development
- [ ] Admin tools and monitoring

### Phase 5: Testing & Launch (2-3 weeks)

- [ ] Integration testing
- [ ] Performance optimization
- [ ] Documentation
- [ ] Self-hosting guide
- [ ] Initial launch with community testers

## Technical Stack

- **Backend**: Python (Discord.py, FastAPI)
- **Database**: MongoDB
- **Infrastructure**: Docker, VPS hosting
- **AI Integration**: OpenAI, Anthropic, self-hosted options
- **Proxy Management**: Rotating proxy system

## Implementation Priorities Based on User Feedback

1. **Memory System**: The most requested feature - automatic generation and management of character memory
2. **Lorebook/Knowledge**: Context-aware information triggered by keywords
3. **Social Experience**: Multiple bots in the same server with consistent personalities
4. **Voice Integration**: Quick and easy voice functionality
5. **Flexible Character Creation**: Detailed system prompt customization

## Next Steps

1. Finalize the character bot implementation with memory and lorebook features
2. Develop the bot manager with containerization support
3. Begin work on the web portal for character management
4. Test with a small group of users before full launch

## Cost Projections

- Existing VPS: $0 (already paid for)
- MongoDB: Self-hosted on VPS ($0)
- Proxies: $3/month for 100 IPs
- Miscellaneous: ~$10-20/month

**Total Monthly Overhead**: ~$15-25

With the tiered pricing model, the platform would need only 15-25 users at the $1/mo tier to break even, making this a viable business opportunity while still providing a free open-source alternative.
