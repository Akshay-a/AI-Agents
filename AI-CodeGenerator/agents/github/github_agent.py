"""
GitHub Repository Agent
Handles GitHub authentication, repository discovery, and cloning operations.
"""

import os
import git
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
import tempfile
import shutil

from ..base.agent_interface import BaseAgent, AgentInput, AgentOutput, AgentStatus


class GitHubAgent(BaseAgent):
    """
    GitHub Repository Agent for authentication, repository listing, and cloning.
    
    Capabilities:
    - GitHub OAuth authentication
    - Repository listing with metadata
    - Repository cloning to local filesystem
    - Technology stack detection
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id="github_repository_agent", config=config)
        
        # GitHub API configuration
        self.api_base_url = "https://api.github.com"
        self.github_token = None
        self.session = requests.Session()
        
        # Local storage configuration
        self.workspace_base = config.get('workspace_base', '/tmp/github_agent_workspace') if config else '/tmp/github_agent_workspace'
        os.makedirs(self.workspace_base, exist_ok=True)

    def validate_input(self, agent_input: AgentInput) -> bool:
        """Validate GitHub agent specific input requirements"""
        data = agent_input.data
        operation = data.get('operation')
        
        if not operation:
            self.logger.error("Missing 'operation' field in input data")
            return False
            
        if operation not in ['authenticate', 'list_repositories', 'clone_repository']:
            self.logger.error(f"Invalid operation: {operation}")
            return False
            
        # Validate operation-specific requirements
        if operation == 'authenticate':
            return 'github_token' in data
        elif operation == 'list_repositories':
            return self.github_token is not None
        elif operation == 'clone_repository':
            required_fields = ['repository_url', 'session_id']
            return all(field in data for field in required_fields)
            
        return True

    def process(self, agent_input: AgentInput) -> AgentOutput:
        """Main processing method for GitHub operations"""
        start_time = agent_input.timestamp
        data = agent_input.data
        operation = data.get('operation')
        
        try:
            if operation == 'authenticate':
                result = self._authenticate(data.get('github_token'))
            elif operation == 'list_repositories':
                result = self._list_repositories(data.get('sort_by', 'updated'))
            elif operation == 'clone_repository':
                result = self._clone_repository(
                    data.get('repository_url'),
                    data.get('branch', 'main'),
                    agent_input.session_id
                )
            else:
                raise ValueError(f"Unsupported operation: {operation}")
                
            return self._create_success_output(
                agent_input.session_id,
                start_time,
                result,
                metadata={'operation': operation}
            )
            
        except Exception as e:
            self.logger.error(f"GitHub operation failed: {str(e)}")
            raise

    def _authenticate(self, token: str) -> Dict[str, Any]:
        """Authenticate with GitHub using provided token"""
        self.github_token = token
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        })
        
        # Test authentication by getting user info
        response = self.session.get(f"{self.api_base_url}/user")
        response.raise_for_status()
        
        user_info = response.json()
        
        self.logger.info(f"Successfully authenticated as {user_info.get('login')}")
        
        return {
            'authenticated': True,
            'user': {
                'login': user_info.get('login'),
                'name': user_info.get('name'),
                'email': user_info.get('email'),
                'public_repos': user_info.get('public_repos'),
                'private_repos': user_info.get('total_private_repos', 0)
            }
        }

    def _list_repositories(self, sort_by: str = 'updated') -> Dict[str, Any]:
        """List user repositories sorted by specified criteria"""
        if not self.github_token:
            raise ValueError("Not authenticated. Call authenticate first.")
        
        repositories = []
        page = 1
        per_page = 100
        
        while True:
            # Get repositories with pagination
            params = {
                'sort': sort_by,
                'direction': 'desc',
                'per_page': per_page,
                'page': page,
                'type': 'all'  # Include both public and private repos
            }
            
            response = self.session.get(f"{self.api_base_url}/user/repos", params=params)
            response.raise_for_status()
            
            repos_batch = response.json()
            
            if not repos_batch:
                break
                
            for repo in repos_batch:
                # Get additional metadata for each repo
                repo_info = self._extract_repository_info(repo)
                repositories.append(repo_info)
            
            page += 1
            
            # GitHub API returns up to 100 repos per page
            if len(repos_batch) < per_page:
                break
        
        self.logger.info(f"Retrieved {len(repositories)} repositories")
        
        return {
            'repositories': repositories,
            'total_count': len(repositories),
            'sorted_by': sort_by
        }

    def _extract_repository_info(self, repo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and enhance repository information"""
        # Get language statistics
        languages = self._get_repository_languages(repo_data['languages_url'])
        
        return {
            'id': repo_data['id'],
            'name': repo_data['name'],
            'full_name': repo_data['full_name'],
            'description': repo_data.get('description', ''),
            'private': repo_data['private'],
            'language': repo_data.get('language'),
            'languages': languages,
            'size': repo_data['size'],  # Size in KB
            'last_commit': repo_data['updated_at'],
            'created_at': repo_data['created_at'],
            'default_branch': repo_data['default_branch'],
            'clone_url': repo_data['clone_url'],
            'ssh_url': repo_data['ssh_url'],
            'html_url': repo_data['html_url'],
            'stars': repo_data['stargazers_count'],
            'forks': repo_data['forks_count'],
            'open_issues': repo_data['open_issues_count'],
            'topics': repo_data.get('topics', []),
            'archived': repo_data['archived'],
            'technology_stack': self._detect_technology_stack(languages, repo_data.get('topics', []))
        }

    def _get_repository_languages(self, languages_url: str) -> Dict[str, int]:
        """Get programming languages used in repository"""
        try:
            response = self.session.get(languages_url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.warning(f"Could not fetch languages: {str(e)}")
            return {}

    def _detect_technology_stack(self, languages: Dict[str, int], topics: List[str]) -> List[str]:
        """Detect technology stack based on languages and topics"""
        stack = []
        
        # Add primary languages
        if languages:
            # Sort by bytes of code and take top languages
            sorted_languages = sorted(languages.items(), key=lambda x: x[1], reverse=True)
            for lang, _ in sorted_languages[:3]:  # Top 3 languages
                stack.append(lang)
        
        # Add framework/technology detection based on topics
        framework_map = {
            'react': 'React',
            'angular': 'Angular',
            'vue': 'Vue.js',
            'express': 'Express.js',
            'flask': 'Flask',
            'django': 'Django',
            'spring': 'Spring',
            'laravel': 'Laravel',
            'rails': 'Ruby on Rails',
            'nodejs': 'Node.js',
            'docker': 'Docker',
            'kubernetes': 'Kubernetes'
        }
        
        for topic in topics:
            if topic.lower() in framework_map:
                framework = framework_map[topic.lower()]
                if framework not in stack:
                    stack.append(framework)
        
        return stack

    def _clone_repository(self, repository_url: str, branch: str, session_id: str) -> Dict[str, Any]:
        """Clone repository to local filesystem"""
        if not self.github_token:
            raise ValueError("Not authenticated. Call authenticate first.")
        
        # Create session-specific directory
        session_dir = os.path.join(self.workspace_base, session_id)
        repo_dir = os.path.join(session_dir, 'repository')
        
        # Clean up existing directory if it exists
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
        
        os.makedirs(session_dir, exist_ok=True)
        
        try:
            # Prepare authenticated URL
            if repository_url.startswith('https://github.com/'):
                auth_url = repository_url.replace(
                    'https://github.com/',
                    f'https://{self.github_token}@github.com/'
                )
            else:
                auth_url = repository_url
            
            self.logger.info(f"Cloning repository to {repo_dir}")
            
            # Clone the repository
            repo = git.Repo.clone_from(auth_url, repo_dir, branch=branch)
            
            # Analyze the cloned repository
            analysis = self._analyze_repository_structure(repo_dir)
            
            return {
                'cloned': True,
                'local_path': repo_dir,
                'session_dir': session_dir,
                'branch': branch,
                'commit_hash': repo.head.commit.hexsha,
                'commit_message': repo.head.commit.message.strip(),
                'analysis': analysis
            }
            
        except Exception as e:
            # Clean up on failure
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
            raise ValueError(f"Failed to clone repository: {str(e)}")

    def _analyze_repository_structure(self, repo_path: str) -> Dict[str, Any]:
        """Analyze cloned repository structure"""
        analysis = {
            'total_files': 0,
            'source_files': 0,
            'config_files': 0,
            'documentation_files': 0,
            'file_types': {},
            'directories': [],
            'entry_points': [],
            'dependencies': {}
        }
        
        # File extension mappings
        source_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.go', '.rs', '.php', '.rb'}
        config_extensions = {'.json', '.yml', '.yaml', '.xml', '.ini', '.cfg', '.toml'}
        doc_extensions = {'.md', '.txt', '.rst', '.doc', '.docx'}
        
        for root, dirs, files in os.walk(repo_path):
            # Skip .git directory
            if '.git' in dirs:
                dirs.remove('.git')
            
            # Record directories
            rel_root = os.path.relpath(root, repo_path)
            if rel_root != '.':
                analysis['directories'].append(rel_root)
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                
                analysis['total_files'] += 1
                
                # Get file extension
                _, ext = os.path.splitext(file)
                ext = ext.lower()
                
                # Count by type
                if ext in source_extensions:
                    analysis['source_files'] += 1
                elif ext in config_extensions:
                    analysis['config_files'] += 1
                elif ext in doc_extensions:
                    analysis['documentation_files'] += 1
                
                # Count by extension
                analysis['file_types'][ext] = analysis['file_types'].get(ext, 0) + 1
                
                # Detect entry points
                if file.lower() in ['main.py', 'app.py', 'index.js', 'main.js', 'server.js', 'main.java']:
                    analysis['entry_points'].append(rel_path)
        
        # Detect dependencies
        analysis['dependencies'] = self._detect_dependencies(repo_path)
        
        return analysis

    def _detect_dependencies(self, repo_path: str) -> Dict[str, Any]:
        """Detect project dependencies from common files"""
        dependencies = {}
        
        # Python dependencies
        requirements_files = ['requirements.txt', 'Pipfile', 'pyproject.toml']
        for req_file in requirements_files:
            req_path = os.path.join(repo_path, req_file)
            if os.path.exists(req_path):
                dependencies['python'] = req_file
                break
        
        # Node.js dependencies
        package_json = os.path.join(repo_path, 'package.json')
        if os.path.exists(package_json):
            dependencies['nodejs'] = 'package.json'
        
        # Java dependencies
        java_files = ['pom.xml', 'build.gradle', 'build.gradle.kts']
        for java_file in java_files:
            java_path = os.path.join(repo_path, java_file)
            if os.path.exists(java_path):
                dependencies['java'] = java_file
                break
        
        # .NET dependencies
        dotnet_files = ['*.csproj', '*.sln', 'packages.config']
        for pattern in dotnet_files:
            import glob
            matches = glob.glob(os.path.join(repo_path, pattern))
            if matches:
                dependencies['dotnet'] = os.path.basename(matches[0])
                break
        
        return dependencies

    def cleanup_session(self, session_id: str) -> bool:
        """Clean up session-specific files and directories"""
        session_dir = os.path.join(self.workspace_base, session_id)
        
        try:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                self.logger.info(f"Cleaned up session directory: {session_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to cleanup session {session_id}: {str(e)}")
            return False

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session's workspace"""
        session_dir = os.path.join(self.workspace_base, session_id)
        
        if not os.path.exists(session_dir):
            return None
        
        repo_dir = os.path.join(session_dir, 'repository')
        
        return {
            'session_id': session_id,
            'session_dir': session_dir,
            'repository_dir': repo_dir,
            'repository_exists': os.path.exists(repo_dir),
            'created_at': datetime.fromtimestamp(os.path.getctime(session_dir)).isoformat()
        } 