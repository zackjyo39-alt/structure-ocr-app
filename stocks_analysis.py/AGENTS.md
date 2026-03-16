# AGENTS

<skills_system priority="1">

## Available Skills

<!-- SKILLS_TABLE_START -->
<usage>
When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

How to use skills:
- Invoke: Bash("openskills read <skill-name>")
- The skill content will load with detailed instructions on how to complete the task
- Base directory provided in output for resolving bundled resources (references/, scripts/, assets/)

Usage notes:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already loaded in your context
- Each skill invocation is stateless
</usage>

<available_skills>

<skill>
<name>accessibility-compliance</name>
<description>Implement WCAG 2.2 compliant interfaces with mobile accessibility, inclusive design patterns, and assistive technology support. Use when auditing accessibility, implementing ARIA patterns, building for screen readers, or ensuring inclusive user experiences.</description>
<location>global</location>
</skill>

<skill>
<name>airflow-dag-patterns</name>
<description>Build production Apache Airflow DAGs with best practices for operators, sensors, testing, and deployment. Use when creating data pipelines, orchestrating workflows, or scheduling batch jobs.</description>
<location>global</location>
</skill>

<skill>
<name>angular-migration</name>
<description>Migrate from AngularJS to Angular using hybrid mode, incremental component rewriting, and dependency injection updates. Use when upgrading AngularJS applications, planning framework migrations, or modernizing legacy Angular code.</description>
<location>global</location>
</skill>

<skill>
<name>anti-reversing-techniques</name>
<description>Understand anti-reversing, obfuscation, and protection techniques encountered during software analysis. Use when analyzing protected binaries, bypassing anti-debugging for authorized analysis, or understanding software protection mechanisms.</description>
<location>global</location>
</skill>

<skill>
<name>api-design-principles</name>
<description>Master REST and GraphQL API design principles to build intuitive, scalable, and maintainable APIs that delight developers. Use when designing new APIs, reviewing API specifications, or establishing API design standards.</description>
<location>global</location>
</skill>

<skill>
<name>architecture-decision-records</name>
<description>Write and maintain Architecture Decision Records (ADRs) following best practices for technical decision documentation. Use when documenting significant technical decisions, reviewing past architectural choices, or establishing decision processes.</description>
<location>global</location>
</skill>

<skill>
<name>architecture-patterns</name>
<description>Implement proven backend architecture patterns including Clean Architecture, Hexagonal Architecture, and Domain-Driven Design. Use when architecting complex backend systems or refactoring existing applications for better maintainability.</description>
<location>global</location>
</skill>

<skill>
<name>async-python-patterns</name>
<description>Master Python asyncio, concurrent programming, and async/await patterns for high-performance applications. Use when building async APIs, concurrent systems, or I/O-bound applications requiring non-blocking operations.</description>
<location>global</location>
</skill>

<skill>
<name>attack-tree-construction</name>
<description>Build comprehensive attack trees to visualize threat paths. Use when mapping attack scenarios, identifying defense gaps, or communicating security risks to stakeholders.</description>
<location>global</location>
</skill>

<skill>
<name>auth-implementation-patterns</name>
<description>Master authentication and authorization patterns including JWT, OAuth2, session management, and RBAC to build secure, scalable access control systems. Use when implementing auth systems, securing APIs, or debugging security issues.</description>
<location>global</location>
</skill>

<skill>
<name>backtesting-frameworks</name>
<description>Build robust backtesting systems for trading strategies with proper handling of look-ahead bias, survivorship bias, and transaction costs. Use when developing trading algorithms, validating strategies, or building backtesting infrastructure.</description>
<location>global</location>
</skill>

<skill>
<name>bash-defensive-patterns</name>
<description>Master defensive Bash programming techniques for production-grade scripts. Use when writing robust shell scripts, CI/CD pipelines, or system utilities requiring fault tolerance and safety.</description>
<location>global</location>
</skill>

<skill>
<name>bats-testing-patterns</name>
<description>Master Bash Automated Testing System (Bats) for comprehensive shell script testing. Use when writing tests for shell scripts, CI/CD pipelines, or requiring test-driven development of shell utilities.</description>
<location>global</location>
</skill>

<skill>
<name>bazel-build-optimization</name>
<description>Optimize Bazel builds for large-scale monorepos. Use when configuring Bazel, implementing remote execution, or optimizing build performance for enterprise codebases.</description>
<location>global</location>
</skill>

<skill>
<name>billing-automation</name>
<description>Build automated billing systems for recurring payments, invoicing, subscription lifecycle, and dunning management. Use when implementing subscription billing, automating invoicing, or managing recurring payment systems.</description>
<location>global</location>
</skill>

<skill>
<name>binary-analysis-patterns</name>
<description>Master binary analysis patterns including disassembly, decompilation, control flow analysis, and code pattern recognition. Use when analyzing executables, understanding compiled code, or performing static analysis on binaries.</description>
<location>global</location>
</skill>

<skill>
<name>brainstorming</name>
<description>"You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."</description>
<location>global</location>
</skill>

<skill>
<name>changelog-automation</name>
<description>Automate changelog generation from commits, PRs, and releases following Keep a Changelog format. Use when setting up release workflows, generating release notes, or standardizing commit conventions.</description>
<location>global</location>
</skill>

<skill>
<name>code-review-excellence</name>
<description>Master effective code review practices to provide constructive feedback, catch bugs early, and foster knowledge sharing while maintaining team morale. Use when reviewing pull requests, establishing review standards, or mentoring developers.</description>
<location>global</location>
</skill>

<skill>
<name>competitive-landscape</name>
<description>This skill should be used when the user asks to "analyze competitors", "assess competitive landscape", "identify differentiation", "evaluate market positioning", "apply Porter's Five Forces", or requests competitive strategy analysis.</description>
<location>global</location>
</skill>

<skill>
<name>context-driven-development</name>
<description>Use this skill when working with Conductor's context-driven development methodology, managing project context artifacts, or understanding the relationship between product.md, tech-stack.md, and workflow.md files.</description>
<location>global</location>
</skill>

<skill>
<name>cost-optimization</name>
<description>Optimize cloud costs through resource rightsizing, tagging strategies, reserved instances, and spending analysis. Use when reducing cloud expenses, analyzing infrastructure costs, or implementing cost governance policies.</description>
<location>global</location>
</skill>

<skill>
<name>cqrs-implementation</name>
<description>Implement Command Query Responsibility Segregation for scalable architectures. Use when separating read and write models, optimizing query performance, or building event-sourced systems.</description>
<location>global</location>
</skill>

<skill>
<name>data-quality-frameworks</name>
<description>Implement data quality validation with Great Expectations, dbt tests, and data contracts. Use when building data quality pipelines, implementing validation rules, or establishing data contracts.</description>
<location>global</location>
</skill>

<skill>
<name>data-storytelling</name>
<description>Transform data into compelling narratives using visualization, context, and persuasive structure. Use when presenting analytics to stakeholders, creating data reports, or building executive presentations.</description>
<location>global</location>
</skill>

<skill>
<name>database-migration</name>
<description>Execute database migrations across ORMs and platforms with zero-downtime strategies, data transformation, and rollback procedures. Use when migrating databases, changing schemas, performing data transformations, or implementing zero-downtime deployment strategies.</description>
<location>global</location>
</skill>

<skill>
<name>dbt-transformation-patterns</name>
<description>Master dbt (data build tool) for analytics engineering with model organization, testing, documentation, and incremental strategies. Use when building data transformations, creating data models, or implementing analytics engineering best practices.</description>
<location>global</location>
</skill>

<skill>
<name>debugging-strategies</name>
<description>Master systematic debugging techniques, profiling tools, and root cause analysis to efficiently track down bugs across any codebase or technology stack. Use when investigating bugs, performance issues, or unexpected behavior.</description>
<location>global</location>
</skill>

<skill>
<name>defi-protocol-templates</name>
<description>Implement DeFi protocols with production-ready templates for staking, AMMs, governance, and lending systems. Use when building decentralized finance applications or smart contract protocols.</description>
<location>global</location>
</skill>

<skill>
<name>dependency-upgrade</name>
<description>Manage major dependency version upgrades with compatibility analysis, staged rollout, and comprehensive testing. Use when upgrading framework versions, updating major dependencies, or managing breaking changes in libraries.</description>
<location>global</location>
</skill>

<skill>
<name>deployment-pipeline-design</name>
<description>Design multi-stage CI/CD pipelines with approval gates, security checks, and deployment orchestration. Use when architecting deployment workflows, setting up continuous delivery, or implementing GitOps practices.</description>
<location>global</location>
</skill>

<skill>
<name>design-system-patterns</name>
<description>Build scalable design systems with design tokens, theming infrastructure, and component architecture patterns. Use when creating design tokens, implementing theme switching, building component libraries, or establishing design system foundations.</description>
<location>global</location>
</skill>

<skill>
<name>dispatching-parallel-agents</name>
<description>Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies</description>
<location>global</location>
</skill>

<skill>
<name>distributed-tracing</name>
<description>Implement distributed tracing with Jaeger and Tempo to track requests across microservices and identify performance bottlenecks. Use when debugging microservices, analyzing request flows, or implementing observability for distributed systems.</description>
<location>global</location>
</skill>

<skill>
<name>dotnet-backend-patterns</name>
<description>Master C#/.NET backend development patterns for building robust APIs, MCP servers, and enterprise applications. Covers async/await, dependency injection, Entity Framework Core, Dapper, configuration, caching, and testing with xUnit. Use when developing .NET backends, reviewing C# code, or designing API architectures.</description>
<location>global</location>
</skill>

<skill>
<name>e2e-testing-patterns</name>
<description>Master end-to-end testing with Playwright and Cypress to build reliable test suites that catch bugs, improve confidence, and enable fast deployment. Use when implementing E2E tests, debugging flaky tests, or establishing testing standards.</description>
<location>global</location>
</skill>

<skill>
<name>embedding-strategies</name>
<description>Select and optimize embedding models for semantic search and RAG applications. Use when choosing embedding models, implementing chunking strategies, or optimizing embedding quality for specific domains.</description>
<location>global</location>
</skill>

<skill>
<name>employment-contract-templates</name>
<description>Create employment contracts, offer letters, and HR policy documents following legal best practices. Use when drafting employment agreements, creating HR policies, or standardizing employment documentation.</description>
<location>global</location>
</skill>

<skill>
<name>error-handling-patterns</name>
<description>Master error handling patterns across languages including exceptions, Result types, error propagation, and graceful degradation to build resilient applications. Use when implementing error handling, designing APIs, or improving application reliability.</description>
<location>global</location>
</skill>

<skill>
<name>event-store-design</name>
<description>Design and implement event stores for event-sourced systems. Use when building event sourcing infrastructure, choosing event store technologies, or implementing event persistence patterns.</description>
<location>global</location>
</skill>

<skill>
<name>executing-plans</name>
<description>Use when you have a written implementation plan to execute in a separate session with review checkpoints</description>
<location>global</location>
</skill>

<skill>
<name>fastapi-templates</name>
<description>Create production-ready FastAPI projects with async patterns, dependency injection, and comprehensive error handling. Use when building new FastAPI applications or setting up backend API projects.</description>
<location>global</location>
</skill>

<skill>
<name>finishing-a-development-branch</name>
<description>Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides completion of development work by presenting structured options for merge, PR, or cleanup</description>
<location>global</location>
</skill>

<skill>
<name>gdpr-data-handling</name>
<description>Implement GDPR-compliant data handling with consent management, data subject rights, and privacy by design. Use when building systems that process EU personal data, implementing privacy controls, or conducting GDPR compliance reviews.</description>
<location>global</location>
</skill>

<skill>
<name>git-advanced-workflows</name>
<description>Master advanced Git workflows including rebasing, cherry-picking, bisect, worktrees, and reflog to maintain clean history and recover from any situation. Use when managing complex Git histories, collaborating on feature branches, or troubleshooting repository issues.</description>
<location>global</location>
</skill>

<skill>
<name>github-actions-templates</name>
<description>Create production-ready GitHub Actions workflows for automated testing, building, and deploying applications. Use when setting up CI/CD with GitHub Actions, automating development workflows, or creating reusable workflow templates.</description>
<location>global</location>
</skill>

<skill>
<name>gitlab-ci-patterns</name>
<description>Build GitLab CI/CD pipelines with multi-stage workflows, caching, and distributed runners for scalable automation. Use when implementing GitLab CI/CD, optimizing pipeline performance, or setting up automated testing and deployment.</description>
<location>global</location>
</skill>

<skill>
<name>gitops-workflow</name>
<description>Implement GitOps workflows with ArgoCD and Flux for automated, declarative Kubernetes deployments with continuous reconciliation. Use when implementing GitOps practices, automating Kubernetes deployments, or setting up declarative infrastructure management.</description>
<location>global</location>
</skill>

<skill>
<name>go-concurrency-patterns</name>
<description>Master Go concurrency with goroutines, channels, sync primitives, and context. Use when building concurrent Go applications, implementing worker pools, or debugging race conditions.</description>
<location>global</location>
</skill>

<skill>
<name>godot-gdscript-patterns</name>
<description>Master Godot 4 GDScript patterns including signals, scenes, state machines, and optimization. Use when building Godot games, implementing game systems, or learning GDScript best practices.</description>
<location>global</location>
</skill>

<skill>
<name>grafana-dashboards</name>
<description>Create and manage production Grafana dashboards for real-time visualization of system and application metrics. Use when building monitoring dashboards, visualizing metrics, or creating operational observability interfaces.</description>
<location>global</location>
</skill>

<skill>
<name>helm-chart-scaffolding</name>
<description>Design, organize, and manage Helm charts for templating and packaging Kubernetes applications with reusable configurations. Use when creating Helm charts, packaging Kubernetes applications, or implementing templated deployments.</description>
<location>global</location>
</skill>

<skill>
<name>hybrid-cloud-networking</name>
<description>Configure secure, high-performance connectivity between on-premises infrastructure and cloud platforms using VPN and dedicated connections. Use when building hybrid cloud architectures, connecting data centers to cloud, or implementing secure cross-premises networking.</description>
<location>global</location>
</skill>

<skill>
<name>hybrid-search-implementation</name>
<description>Combine vector and keyword search for improved retrieval. Use when implementing RAG systems, building search engines, or when neither approach alone provides sufficient recall.</description>
<location>global</location>
</skill>

<skill>
<name>incident-runbook-templates</name>
<description>Create structured incident response runbooks with step-by-step procedures, escalation paths, and recovery actions. Use when building runbooks, responding to incidents, or establishing incident response procedures.</description>
<location>global</location>
</skill>

<skill>
<name>interaction-design</name>
<description>Design and implement microinteractions, motion design, transitions, and user feedback patterns. Use when adding polish to UI interactions, implementing loading states, or creating delightful user experiences.</description>
<location>global</location>
</skill>

<skill>
<name>istio-traffic-management</name>
<description>Configure Istio traffic management including routing, load balancing, circuit breakers, and canary deployments. Use when implementing service mesh traffic policies, progressive delivery, or resilience patterns.</description>
<location>global</location>
</skill>

<skill>
<name>javascript-testing-patterns</name>
<description>Implement comprehensive testing strategies using Jest, Vitest, and Testing Library for unit tests, integration tests, and end-to-end testing with mocking, fixtures, and test-driven development. Use when writing JavaScript/TypeScript tests, setting up test infrastructure, or implementing TDD/BDD workflows.</description>
<location>global</location>
</skill>

<skill>
<name>k8s-manifest-generator</name>
<description>Create production-ready Kubernetes manifests for Deployments, Services, ConfigMaps, and Secrets following best practices and security standards. Use when generating Kubernetes YAML manifests, creating K8s resources, or implementing production-grade Kubernetes configurations.</description>
<location>global</location>
</skill>

<skill>
<name>k8s-security-policies</name>
<description>Implement Kubernetes security policies including NetworkPolicy, PodSecurityPolicy, and RBAC for production-grade security. Use when securing Kubernetes clusters, implementing network isolation, or enforcing pod security standards.</description>
<location>global</location>
</skill>

<skill>
<name>kpi-dashboard-design</name>
<description>Design effective KPI dashboards with metrics selection, visualization best practices, and real-time monitoring patterns. Use when building business dashboards, selecting metrics, or designing data visualization layouts.</description>
<location>global</location>
</skill>

<skill>
<name>langchain-architecture</name>
<description>Design LLM applications using LangChain 1.x and LangGraph for agents, memory, and tool integration. Use when building LangChain applications, implementing AI agents, or creating complex LLM workflows.</description>
<location>global</location>
</skill>

<skill>
<name>linkerd-patterns</name>
<description>Implement Linkerd service mesh patterns for lightweight, security-focused service mesh deployments. Use when setting up Linkerd, configuring traffic policies, or implementing zero-trust networking with minimal overhead.</description>
<location>global</location>
</skill>

<skill>
<name>llm-evaluation</name>
<description>Implement comprehensive evaluation strategies for LLM applications using automated metrics, human feedback, and benchmarking. Use when testing LLM performance, measuring AI application quality, or establishing evaluation frameworks.</description>
<location>global</location>
</skill>

<skill>
<name>market-sizing-analysis</name>
<description>This skill should be used when the user asks to "calculate TAM", "determine SAM", "estimate SOM", "size the market", "calculate market opportunity", "what's the total addressable market", or requests market sizing analysis for a startup or business opportunity.</description>
<location>global</location>
</skill>

<skill>
<name>memory-forensics</name>
<description>Master memory forensics techniques including memory acquisition, process analysis, and artifact extraction using Volatility and related tools. Use when analyzing memory dumps, investigating incidents, or performing malware analysis from RAM captures.</description>
<location>global</location>
</skill>

<skill>
<name>memory-safety-patterns</name>
<description>Implement memory-safe programming with RAII, ownership, smart pointers, and resource management across Rust, C++, and C. Use when writing safe systems code, managing resources, or preventing memory bugs.</description>
<location>global</location>
</skill>

<skill>
<name>microservices-patterns</name>
<description>Design microservices architectures with service boundaries, event-driven communication, and resilience patterns. Use when building distributed systems, decomposing monoliths, or implementing microservices.</description>
<location>global</location>
</skill>

<skill>
<name>ml-pipeline-workflow</name>
<description>Build end-to-end MLOps pipelines from data preparation through model training, validation, and production deployment. Use when creating ML pipelines, implementing MLOps practices, or automating model training and deployment workflows.</description>
<location>global</location>
</skill>

<skill>
<name>mobile-android-design</name>
<description>Master Material Design 3 and Jetpack Compose patterns for building native Android apps. Use when designing Android interfaces, implementing Compose UI, or following Google's Material Design guidelines.</description>
<location>global</location>
</skill>

<skill>
<name>mobile-ios-design</name>
<description>Master iOS Human Interface Guidelines and SwiftUI patterns for building native iOS apps. Use when designing iOS interfaces, implementing SwiftUI views, or ensuring apps follow Apple's design principles.</description>
<location>global</location>
</skill>

<skill>
<name>modern-javascript-patterns</name>
<description>Master ES6+ features including async/await, destructuring, spread operators, arrow functions, promises, modules, iterators, generators, and functional programming patterns for writing clean, efficient JavaScript code. Use when refactoring legacy code, implementing modern patterns, or optimizing JavaScript applications.</description>
<location>global</location>
</skill>

<skill>
<name>monorepo-management</name>
<description>Master monorepo management with Turborepo, Nx, and pnpm workspaces to build efficient, scalable multi-package repositories with optimized builds and dependency management. Use when setting up monorepos, optimizing builds, or managing shared dependencies.</description>
<location>global</location>
</skill>

<skill>
<name>mtls-configuration</name>
<description>Configure mutual TLS (mTLS) for zero-trust service-to-service communication. Use when implementing zero-trust networking, certificate management, or securing internal service communication.</description>
<location>global</location>
</skill>

<skill>
<name>multi-cloud-architecture</name>
<description>Design multi-cloud architectures using a decision framework to select and integrate services across AWS, Azure, and GCP. Use when building multi-cloud systems, avoiding vendor lock-in, or leveraging best-of-breed services from multiple providers.</description>
<location>global</location>
</skill>

<skill>
<name>nextjs-app-router-patterns</name>
<description>Master Next.js 14+ App Router with Server Components, streaming, parallel routes, and advanced data fetching. Use when building Next.js applications, implementing SSR/SSG, or optimizing React Server Components.</description>
<location>global</location>
</skill>

<skill>
<name>nft-standards</name>
<description>Implement NFT standards (ERC-721, ERC-1155) with proper metadata handling, minting strategies, and marketplace integration. Use when creating NFT contracts, building NFT marketplaces, or implementing digital asset systems.</description>
<location>global</location>
</skill>

<skill>
<name>nodejs-backend-patterns</name>
<description>Build production-ready Node.js backend services with Express/Fastify, implementing middleware patterns, error handling, authentication, database integration, and API design best practices. Use when creating Node.js servers, REST APIs, GraphQL backends, or microservices architectures.</description>
<location>global</location>
</skill>

<skill>
<name>nx-workspace-patterns</name>
<description>Configure and optimize Nx monorepo workspaces. Use when setting up Nx, configuring project boundaries, optimizing build caching, or implementing affected commands.</description>
<location>global</location>
</skill>

<skill>
<name>on-call-handoff-patterns</name>
<description>Master on-call shift handoffs with context transfer, escalation procedures, and documentation. Use when transitioning on-call responsibilities, documenting shift summaries, or improving on-call processes.</description>
<location>global</location>
</skill>

<skill>
<name>openapi-spec-generation</name>
<description>Generate and maintain OpenAPI 3.1 specifications from code, design-first specs, and validation patterns. Use when creating API documentation, generating SDKs, or ensuring API contract compliance.</description>
<location>global</location>
</skill>

<skill>
<name>paypal-integration</name>
<description>Integrate PayPal payment processing with support for express checkout, subscriptions, and refund management. Use when implementing PayPal payments, processing online transactions, or building e-commerce checkout flows.</description>
<location>global</location>
</skill>

<skill>
<name>pci-compliance</name>
<description>Implement PCI DSS compliance requirements for secure handling of payment card data and payment systems. Use when securing payment processing, achieving PCI compliance, or implementing payment card security measures.</description>
<location>global</location>
</skill>

<skill>
<name>postgresql</name>
<description>Design a PostgreSQL-specific schema. Covers best-practices, data types, indexing, constraints, performance patterns, and advanced features</description>
<location>global</location>
</skill>

<skill>
<name>postmortem-writing</name>
<description>Write effective blameless postmortems with root cause analysis, timelines, and action items. Use when conducting incident reviews, writing postmortem documents, or improving incident response processes.</description>
<location>global</location>
</skill>

<skill>
<name>projection-patterns</name>
<description>Build read models and projections from event streams. Use when implementing CQRS read sides, building materialized views, or optimizing query performance in event-sourced systems.</description>
<location>global</location>
</skill>

<skill>
<name>prometheus-configuration</name>
<description>Set up Prometheus for comprehensive metric collection, storage, and monitoring of infrastructure and applications. Use when implementing metrics collection, setting up monitoring infrastructure, or configuring alerting systems.</description>
<location>global</location>
</skill>

<skill>
<name>prompt-engineering-patterns</name>
<description>Master advanced prompt engineering techniques to maximize LLM performance, reliability, and controllability in production. Use when optimizing prompts, improving LLM outputs, or designing production prompt templates.</description>
<location>global</location>
</skill>

<skill>
<name>protocol-reverse-engineering</name>
<description>Master network protocol reverse engineering including packet analysis, protocol dissection, and custom protocol documentation. Use when analyzing network traffic, understanding proprietary protocols, or debugging network communication.</description>
<location>global</location>
</skill>

<skill>
<name>python-packaging</name>
<description>Create distributable Python packages with proper project structure, setup.py/pyproject.toml, and publishing to PyPI. Use when packaging Python libraries, creating CLI tools, or distributing Python code.</description>
<location>global</location>
</skill>

<skill>
<name>python-performance-optimization</name>
<description>Profile and optimize Python code using cProfile, memory profilers, and performance best practices. Use when debugging slow Python code, optimizing bottlenecks, or improving application performance.</description>
<location>global</location>
</skill>

<skill>
<name>python-testing-patterns</name>
<description>Implement comprehensive testing strategies with pytest, fixtures, mocking, and test-driven development. Use when writing Python tests, setting up test suites, or implementing testing best practices.</description>
<location>global</location>
</skill>

<skill>
<name>rag-implementation</name>
<description>Build Retrieval-Augmented Generation (RAG) systems for LLM applications with vector databases and semantic search. Use when implementing knowledge-grounded AI, building document Q&A systems, or integrating LLMs with external knowledge bases.</description>
<location>global</location>
</skill>

<skill>
<name>react-modernization</name>
<description>Upgrade React applications to latest versions, migrate from class components to hooks, and adopt concurrent features. Use when modernizing React codebases, migrating to React Hooks, or upgrading to latest React versions.</description>
<location>global</location>
</skill>

<skill>
<name>react-native-architecture</name>
<description>Build production React Native apps with Expo, navigation, native modules, offline sync, and cross-platform patterns. Use when developing mobile apps, implementing native integrations, or architecting React Native projects.</description>
<location>global</location>
</skill>

<skill>
<name>react-native-design</name>
<description>Master React Native styling, navigation, and Reanimated animations for cross-platform mobile development. Use when building React Native apps, implementing navigation patterns, or creating performant animations.</description>
<location>global</location>
</skill>

<skill>
<name>react-state-management</name>
<description>Master modern React state management with Redux Toolkit, Zustand, Jotai, and React Query. Use when setting up global state, managing server state, or choosing between state management solutions.</description>
<location>global</location>
</skill>

<skill>
<name>receiving-code-review</name>
<description>Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation</description>
<location>global</location>
</skill>

<skill>
<name>requesting-code-review</name>
<description>Use when completing tasks, implementing major features, or before merging to verify work meets requirements</description>
<location>global</location>
</skill>

<skill>
<name>responsive-design</name>
<description>Implement modern responsive layouts using container queries, fluid typography, CSS Grid, and mobile-first breakpoint strategies. Use when building adaptive interfaces, implementing fluid layouts, or creating component-level responsive behavior.</description>
<location>global</location>
</skill>

<skill>
<name>risk-metrics-calculation</name>
<description>Calculate portfolio risk metrics including VaR, CVaR, Sharpe, Sortino, and drawdown analysis. Use when measuring portfolio risk, implementing risk limits, or building risk monitoring systems.</description>
<location>global</location>
</skill>

<skill>
<name>rust-async-patterns</name>
<description>Master Rust async programming with Tokio, async traits, error handling, and concurrent patterns. Use when building async Rust applications, implementing concurrent systems, or debugging async code.</description>
<location>global</location>
</skill>

<skill>
<name>saga-orchestration</name>
<description>Implement saga patterns for distributed transactions and cross-aggregate workflows. Use when coordinating multi-step business processes, handling compensating transactions, or managing long-running workflows.</description>
<location>global</location>
</skill>

<skill>
<name>sast-configuration</name>
<description>Configure Static Application Security Testing (SAST) tools for automated vulnerability detection in application code. Use when setting up security scanning, implementing DevSecOps practices, or automating code vulnerability detection.</description>
<location>global</location>
</skill>

<skill>
<name>screen-reader-testing</name>
<description>Test web applications with screen readers including VoiceOver, NVDA, and JAWS. Use when validating screen reader compatibility, debugging accessibility issues, or ensuring assistive technology support.</description>
<location>global</location>
</skill>

<skill>
<name>secrets-management</name>
<description>Implement secure secrets management for CI/CD pipelines using Vault, AWS Secrets Manager, or native platform solutions. Use when handling sensitive credentials, rotating secrets, or securing CI/CD environments.</description>
<location>global</location>
</skill>

<skill>
<name>security-first-local-secrets</name>
<description>Use when handling credentials, tokens, keys, secrets, or security-sensitive configs in any task, including debugging, testing, logging, or writing files</description>
<location>global</location>
</skill>

<skill>
<name>security-requirement-extraction</name>
<description>Derive security requirements from threat models and business context. Use when translating threats into actionable requirements, creating security user stories, or building security test cases.</description>
<location>global</location>
</skill>

<skill>
<name>service-mesh-observability</name>
<description>Implement comprehensive observability for service meshes including distributed tracing, metrics, and visualization. Use when setting up mesh monitoring, debugging latency issues, or implementing SLOs for service communication.</description>
<location>global</location>
</skill>

<skill>
<name>shellcheck-configuration</name>
<description>Master ShellCheck static analysis configuration and usage for shell script quality. Use when setting up linting infrastructure, fixing code issues, or ensuring script portability.</description>
<location>global</location>
</skill>

<skill>
<name>similarity-search-patterns</name>
<description>Implement efficient similarity search with vector databases. Use when building semantic search, implementing nearest neighbor queries, or optimizing retrieval performance.</description>
<location>global</location>
</skill>

<skill>
<name>slo-implementation</name>
<description>Define and implement Service Level Indicators (SLIs) and Service Level Objectives (SLOs) with error budgets and alerting. Use when establishing reliability targets, implementing SRE practices, or measuring service performance.</description>
<location>global</location>
</skill>

<skill>
<name>solidity-security</name>
<description>Master smart contract security best practices to prevent common vulnerabilities and implement secure Solidity patterns. Use when writing smart contracts, auditing existing contracts, or implementing security measures for blockchain applications.</description>
<location>global</location>
</skill>

<skill>
<name>spark-optimization</name>
<description>Optimize Apache Spark jobs with partitioning, caching, shuffle optimization, and memory tuning. Use when improving Spark performance, debugging slow jobs, or scaling data processing pipelines.</description>
<location>global</location>
</skill>

<skill>
<name>sql-optimization-patterns</name>
<description>Master SQL query optimization, indexing strategies, and EXPLAIN analysis to dramatically improve database performance and eliminate slow queries. Use when debugging slow queries, designing database schemas, or optimizing application performance.</description>
<location>global</location>
</skill>

<skill>
<name>startup-financial-modeling</name>
<description>This skill should be used when the user asks to "create financial projections", "build a financial model", "forecast revenue", "calculate burn rate", "estimate runway", "model cash flow", or requests 3-5 year financial planning for a startup.</description>
<location>global</location>
</skill>

<skill>
<name>startup-metrics-framework</name>
<description>This skill should be used when the user asks about "key startup metrics", "SaaS metrics", "CAC and LTV", "unit economics", "burn multiple", "rule of 40", "marketplace metrics", or requests guidance on tracking and optimizing business performance metrics.</description>
<location>global</location>
</skill>

<skill>
<name>stride-analysis-patterns</name>
<description>Apply STRIDE methodology to systematically identify threats. Use when analyzing system security, conducting threat modeling sessions, or creating security documentation.</description>
<location>global</location>
</skill>

<skill>
<name>stripe-integration</name>
<description>Implement Stripe payment processing for robust, PCI-compliant payment flows including checkout, subscriptions, and webhooks. Use when integrating Stripe payments, building subscription systems, or implementing secure checkout flows.</description>
<location>global</location>
</skill>

<skill>
<name>subagent-driven-development</name>
<description>Use when executing implementation plans with independent tasks in the current session</description>
<location>global</location>
</skill>

<skill>
<name>systematic-debugging</name>
<description>Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes</description>
<location>global</location>
</skill>

<skill>
<name>tailwind-design-system</name>
<description>Build scalable design systems with Tailwind CSS, design tokens, component libraries, and responsive patterns. Use when creating component libraries, implementing design systems, or standardizing UI patterns.</description>
<location>global</location>
</skill>

<skill>
<name>team-composition-analysis</name>
<description>This skill should be used when the user asks to "plan team structure", "determine hiring needs", "design org chart", "calculate compensation", "plan equity allocation", or requests organizational design and headcount planning for a startup.</description>
<location>global</location>
</skill>

<skill>
<name>temporal-python-testing</name>
<description>Test Temporal workflows with pytest, time-skipping, and mocking strategies. Covers unit testing, integration testing, replay testing, and local development setup. Use when implementing Temporal workflow tests or debugging test failures.</description>
<location>global</location>
</skill>

<skill>
<name>terraform-module-library</name>
<description>Build reusable Terraform modules for AWS, Azure, and GCP infrastructure following infrastructure-as-code best practices. Use when creating infrastructure modules, standardizing cloud provisioning, or implementing reusable IaC components.</description>
<location>global</location>
</skill>

<skill>
<name>test-driven-development</name>
<description>Use when implementing any feature or bugfix, before writing implementation code</description>
<location>global</location>
</skill>

<skill>
<name>threat-mitigation-mapping</name>
<description>Map identified threats to appropriate security controls and mitigations. Use when prioritizing security investments, creating remediation plans, or validating control effectiveness.</description>
<location>global</location>
</skill>

<skill>
<name>track-management</name>
<description>Use this skill when creating, managing, or working with Conductor tracks - the logical work units for features, bugs, and refactors. Applies to spec.md, plan.md, and track lifecycle operations.</description>
<location>global</location>
</skill>

<skill>
<name>turborepo-caching</name>
<description>Configure Turborepo for efficient monorepo builds with local and remote caching. Use when setting up Turborepo, optimizing build pipelines, or implementing distributed caching.</description>
<location>global</location>
</skill>

<skill>
<name>typescript-advanced-types</name>
<description>Master TypeScript's advanced type system including generics, conditional types, mapped types, template literals, and utility types for building type-safe applications. Use when implementing complex type logic, creating reusable type utilities, or ensuring compile-time type safety in TypeScript projects.</description>
<location>global</location>
</skill>

<skill>
<name>unity-ecs-patterns</name>
<description>Master Unity ECS (Entity Component System) with DOTS, Jobs, and Burst for high-performance game development. Use when building data-oriented games, optimizing performance, or working with large entity counts.</description>
<location>global</location>
</skill>

<skill>
<name>using-git-worktrees</name>
<description>Use when starting feature work that needs isolation from current workspace or before executing implementation plans - creates isolated git worktrees with smart directory selection and safety verification</description>
<location>global</location>
</skill>

<skill>
<name>using-superpowers</name>
<description>Use when starting any conversation - establishes how to find and use skills, requiring Skill tool invocation before ANY response including clarifying questions</description>
<location>global</location>
</skill>

<skill>
<name>uv-package-manager</name>
<description>Master the uv package manager for fast Python dependency management, virtual environments, and modern Python project workflows. Use when setting up Python projects, managing dependencies, or optimizing Python development workflows with uv.</description>
<location>global</location>
</skill>

<skill>
<name>vector-index-tuning</name>
<description>Optimize vector index performance for latency, recall, and memory. Use when tuning HNSW parameters, selecting quantization strategies, or scaling vector search infrastructure.</description>
<location>global</location>
</skill>

<skill>
<name>verification-before-completion</name>
<description>Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always</description>
<location>global</location>
</skill>

<skill>
<name>visual-design-foundations</name>
<description>Apply typography, color theory, spacing systems, and iconography principles to create cohesive visual designs. Use when establishing design tokens, building style guides, or improving visual hierarchy and consistency.</description>
<location>global</location>
</skill>

<skill>
<name>wcag-audit-patterns</name>
<description>Conduct WCAG 2.2 accessibility audits with automated testing, manual verification, and remediation guidance. Use when auditing websites for accessibility, fixing WCAG violations, or implementing accessible design patterns.</description>
<location>global</location>
</skill>

<skill>
<name>web-component-design</name>
<description>Master React, Vue, and Svelte component patterns including CSS-in-JS, composition strategies, and reusable component architecture. Use when building UI component libraries, designing component APIs, or implementing frontend design systems.</description>
<location>global</location>
</skill>

<skill>
<name>web3-testing</name>
<description>Test smart contracts comprehensively using Hardhat and Foundry with unit tests, integration tests, and mainnet forking. Use when testing Solidity contracts, setting up blockchain test suites, or validating DeFi protocols.</description>
<location>global</location>
</skill>

<skill>
<name>workflow-orchestration-patterns</name>
<description>Design durable workflows with Temporal for distributed systems. Covers workflow vs activity separation, saga patterns, state management, and determinism constraints. Use when building long-running processes, distributed transactions, or microservice orchestration.</description>
<location>global</location>
</skill>

<skill>
<name>workflow-patterns</name>
<description>Use this skill when implementing tasks according to Conductor's TDD workflow, handling phase checkpoints, managing git commits for tasks, or understanding the verification protocol.</description>
<location>global</location>
</skill>

<skill>
<name>writing-plans</name>
<description>Use when you have a spec or requirements for a multi-step task, before touching code</description>
<location>global</location>
</skill>

<skill>
<name>writing-skills</name>
<description>Use when creating new skills, editing existing skills, or verifying skills work before deployment</description>
<location>global</location>
</skill>

</available_skills>
<!-- SKILLS_TABLE_END -->

</skills_system>
