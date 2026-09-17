import json
import os
import urllib.error
import urllib.parse
import urllib.request

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

USERNAME = "MatheusdeCastroViana"
ORGANIZATION = "Kiss-Beauty-Group-Brasil"

PROFILE_TOKEN = os.environ["STATS_TOKEN"]
ORG_TOKEN = os.environ["ORG_STATS_TOKEN"]

REST_API = "https://api.github.com"
GRAPHQL_API = "https://api.github.com/graphql"

API_VERSION = "2026-03-10"

OUTPUT_FILE = Path("profile/github-stats.svg")

CARD_WIDTH = 900
CARD_HEIGHT = 340

LANGUAGE_COLORS = {
    "C#": "#178600",
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "SCSS": "#c6538c",
    "PowerShell": "#012456",
    "Shell": "#89e051",
    "Java": "#b07219",
    "C": "#555555",
    "C++": "#f34b7d",
    "PHP": "#4F5D95",
    "Ruby": "#701516",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "Dart": "#00B4AB",
    "Vue": "#41b883",
    "ABAP": "#E8274B",
    "Dockerfile": "#384d54",
}

FALLBACK_COLORS = [
    "#70a5fd",
    "#bf91f3",
    "#38bdae",
    "#f1e05a",
    "#ff7b72",
    "#a371f7",
    "#39d353",
    "#ffa657",
]

def rest_get(token, path):

    request = urllib.request.Request(
        f"{REST_API}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "MatheusViana-GitHub-Profile",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            content = response.read().decode("utf-8")

            if not content:
                return None

            return json.loads(content)

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"GitHub API retornou HTTP {error.code}. "
            "Verifique as permissões dos tokens."
        ) from None

    except urllib.error.URLError:
        raise RuntimeError(
            "Não foi possível conectar à API do GitHub."
        ) from None


def graphql_request(query, variables):

    payload = json.dumps(
        {
            "query": query,
            "variables": variables,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        GRAPHQL_API,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {PROFILE_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "MatheusViana-GitHub-Profile",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"GraphQL retornou HTTP {error.code}. "
            "Verifique o STATS_TOKEN."
        ) from None

    except urllib.error.URLError:
        raise RuntimeError(
            "Não foi possível conectar à API GraphQL."
        ) from None

    if data.get("errors"):
        raise RuntimeError(
            "O GitHub retornou um erro GraphQL. "
            "Verifique se STATS_TOKEN possui repo e read:user."
        )

    return data["data"]

def get_contribution_years():

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionYears
        }
      }
    }
    """

    data = graphql_request(
        query,
        {
            "login": USERNAME,
        },
    )

    user = data.get("user")

    if not user:
        raise RuntimeError(
            "Usuário do GitHub não encontrado."
        )

    years = (
        user["contributionsCollection"]
        ["contributionYears"]
    )

    return sorted(set(years))


def get_year_contributions(year):

    start = datetime(
        year,
        1,
        1,
        tzinfo=timezone.utc,
    )

    now = datetime.now(timezone.utc)

    if year == now.year:
        end = now
    else:
        end = (
            datetime(
                year + 1,
                1,
                1,
                tzinfo=timezone.utc,
            )
            - timedelta(seconds=1)
        )

    query = """
    query(
      $login: String!,
      $from: DateTime!,
      $to: DateTime!
    ) {
      user(login: $login) {
        contributionsCollection(
          from: $from,
          to: $to
        ) {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          totalPullRequestReviewContributions
        }
      }
    }
    """

    data = graphql_request(
        query,
        {
            "login": USERNAME,
            "from": start.isoformat(),
            "to": end.isoformat(),
        },
    )

    collection = (
        data["user"]
        ["contributionsCollection"]
    )

    return {
        "commits": collection[
            "totalCommitContributions"
        ],
        "pull_requests": collection[
            "totalPullRequestContributions"
        ],
        "issues": collection[
            "totalIssueContributions"
        ],
        "reviews": collection[
            "totalPullRequestReviewContributions"
        ],
    }


def get_all_time_contributions():

    totals = {
        "commits": 0,
        "pull_requests": 0,
        "issues": 0,
        "reviews": 0,
    }

    years = get_contribution_years()

    print(
        f"Anos de contribuição encontrados: {len(years)}"
    )

    for year in years:
        year_data = get_year_contributions(year)

        for key in totals:
            totals[key] += year_data[key]

    return totals
    
def get_personal_repositories():

    repositories = []

    page = 1

    while True:
        data = rest_get(
            PROFILE_TOKEN,
            (
                "/user/repos"
                "?affiliation=owner"
                "&visibility=all"
                "&per_page=100"
                f"&page={page}"
            ),
        )

        if not data:
            break

        for repo in data:
            owner_login = (
                repo.get("owner", {})
                .get("login", "")
            )

            if (
                owner_login.lower()
                != USERNAME.lower()
            ):
                continue

            if repo.get("fork"):
                continue

            if (
                repo.get("name", "").lower()
                == USERNAME.lower()
            ):
                continue

            repositories.append(repo)

        if len(data) < 100:
            break

        page += 1

    return repositories

def get_organization_repositories():
    repositories = []

    page = 1

    while True:
        data = rest_get(
            ORG_TOKEN,
            (
                f"/orgs/{urllib.parse.quote(ORGANIZATION)}"
                "/repos"
                "?type=all"
                "&per_page=100"
                f"&page={page}"
            ),
        )

        if not data:
            break

        for repo in data:
            if repo.get("fork"):
                continue

            repositories.append(repo)

        if len(data) < 100:
            break

        page += 1

    private_count = sum(
        1
        for repo in repositories
        if repo.get("private")
    )

    print(
        "Repositórios da organização visíveis ao token: "
        f"{len(repositories)}"
    )

    print(
        "Repositórios privados visíveis ao token: "
        f"{private_count}"
    )

    if repositories and private_count == 0:
        print(
            "AVISO: nenhum repositório privado foi "
            "identificado. Confira ORG_STATS_TOKEN."
        )

    return repositories


def get_user_contributions_in_repository(repo):

    owner = urllib.parse.quote(
        repo["owner"]["login"],
        safe="",
    )

    repo_name = urllib.parse.quote(
        repo["name"],
        safe="",
    )

    page = 1

    while True:
        data = rest_get(
            ORG_TOKEN,
            (
                f"/repos/{owner}/{repo_name}"
                "/contributors"
                "?per_page=100"
                f"&page={page}"
            ),
        )

        if not data or not isinstance(data, list):
            return 0

        for contributor in data:
            login = contributor.get("login")

            if (
                login
                and login.lower()
                == USERNAME.lower()
            ):
                return int(
                    contributor.get(
                        "contributions",
                        0,
                    )
                )

        if len(data) < 100:
            return 0

        page += 1

def get_repository_languages(repo, token):
    owner = urllib.parse.quote(
        repo["owner"]["login"],
        safe="",
    )

    repo_name = urllib.parse.quote(
        repo["name"],
        safe="",
    )

    data = rest_get(
        token,
        f"/repos/{owner}/{repo_name}/languages",
    )

    if not isinstance(data, dict):
        return {}

    return data


def collect_technology_data():

    language_totals = defaultdict(int)

    personal_repositories = (
        get_personal_repositories()
    )

    personal_projects = 0

    total_stars = 0

    for repo in personal_repositories:
        total_stars += int(
            repo.get("stargazers_count", 0)
        )

        languages = get_repository_languages(
            repo,
            PROFILE_TOKEN,
        )

        if not languages:
            continue

        personal_projects += 1

        for language, byte_count in languages.items():
            language_totals[language] += int(
                byte_count
            )

    organization_repositories = (
        get_organization_repositories()
    )

    organization_projects = 0
    organization_contributions = 0

    for repo in organization_repositories:
        contributions = (
            get_user_contributions_in_repository(
                repo
            )
        )

        if contributions <= 0:
            continue

        languages = get_repository_languages(
            repo,
            ORG_TOKEN,
        )

        if not languages:
            continue

        organization_projects += 1
        organization_contributions += (
            contributions
        )

        for language, byte_count in languages.items():
            language_totals[language] += int(
                byte_count
            )

    return {
        "languages": language_totals,
        "personal_projects": personal_projects,
        "organization_projects":
            organization_projects,
        "organization_contributions":
            organization_contributions,
        "stars": total_stars,
    }

def language_color(language, index):
    return LANGUAGE_COLORS.get(
        language,
        FALLBACK_COLORS[
            index % len(FALLBACK_COLORS)
        ],
    )


def prepare_languages(language_totals):

    total_bytes = sum(
        language_totals.values()
    )

    if total_bytes <= 0:
        return []

    sorted_languages = sorted(
        language_totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    if len(sorted_languages) > 8:
        main_languages = sorted_languages[:7]

        other_bytes = sum(
            item[1]
            for item
            in sorted_languages[7:]
        )

        main_languages.append(
            ("Outros", other_bytes)
        )

        sorted_languages = main_languages

    result = []

    for index, (
        language,
        byte_count,
    ) in enumerate(sorted_languages):
        percentage = (
            byte_count
            / total_bytes
            * 100
        )

        result.append(
            {
                "name": language,
                "percentage": percentage,
                "color": (
                    "#64748b"
                    if language == "Outros"
                    else language_color(
                        language,
                        index,
                    )
                ),
            }
        )

    return result

def format_number(number):
    """
    Formata números no estilo:
    1234 -> 1.234
    """

    return (
        f"{int(number):,}"
        .replace(",", ".")
    )

def generate_svg(
    contribution_totals,
    technology_data,
):
    """
    Gera um único card SVG contendo estatísticas e
    tecnologias.
    """

    languages = prepare_languages(
        technology_data["languages"]
    )

    projects_analyzed = (
        technology_data["personal_projects"]
        + technology_data[
            "organization_projects"
        ]
    )

    stats = [
        (
            "Commits",
            contribution_totals["commits"],
        ),
        (
            "Pull Requests",
            contribution_totals[
                "pull_requests"
            ],
        ),
        (
            "Issues",
            contribution_totals["issues"],
        ),
        (
            "Reviews",
            contribution_totals["reviews"],
        ),
        (
            "Estrelas",
            technology_data["stars"],
        ),
    ]

    stat_parts = []

    stat_width = 160
    stat_height = 72
    gap = 12
    start_x = 24
    stat_y = 76

    for index, (label, value) in enumerate(stats):
        x = start_x + (
            index * (stat_width + gap)
        )

        stat_parts.append(
            f"""
            <rect
                x="{x}"
                y="{stat_y}"
                width="{stat_width}"
                height="{stat_height}"
                rx="8"
                class="stat-box"
            />

            <text
                x="{x + 16}"
                y="{stat_y + 25}"
                class="stat-label"
            >
                {escape(label)}
            </text>

            <text
                x="{x + 16}"
                y="{stat_y + 55}"
                class="stat-value"
            >
                {format_number(value)}
            </text>
            """
        )

    bar_x = 28
    bar_y = 211
    bar_width = CARD_WIDTH - 56
    bar_height = 12

    current_x = bar_x

    bar_parts = []

    for index, language in enumerate(languages):
        segment_width = (
            bar_width
            * language["percentage"]
            / 100
        )

        if index == len(languages) - 1:
            segment_width = (
                bar_x
                + bar_width
                - current_x
            )

        bar_parts.append(
            f"""
            <rect
                x="{current_x:.2f}"
                y="{bar_y}"
                width="{segment_width:.2f}"
                height="{bar_height}"
                fill="{language['color']}"
            />
            """
        )

        current_x += segment_width

    legend_parts = []

    column_width = 212

    for index, language in enumerate(languages):
        column = index % 4
        row = index // 4

        x = 30 + (
            column * column_width
        )

        y = 257 + (
            row * 25
        )

        language_name = escape(
            language["name"]
        )

        percentage = (
            f"{language['percentage']:.1f}%"
        )

        legend_parts.append(
            f"""
            <circle
                cx="{x + 5}"
                cy="{y - 4}"
                r="5"
                fill="{language['color']}"
            />

            <text
                x="{x + 17}"
                y="{y}"
                class="language"
            >
                {language_name} {percentage}
            </text>
            """
        )

    org_projects = (
        technology_data[
            "organization_projects"
        ]
    )

    org_contributions = (
        technology_data[
            "organization_contributions"
        ]
    )

    today = datetime.now().strftime(
        "%d/%m/%Y"
    )

    footer = (
        f"{projects_analyzed} projetos analisados"
        f" • {org_projects} da organização"
        f" • {org_contributions} contribuições detectadas"
        f" • atualizado em {today}"
    )

    svg = f"""<svg
        xmlns="http://www.w3.org/2000/svg"
        width="{CARD_WIDTH}"
        height="{CARD_HEIGHT}"
        viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}"
        role="img"
        aria-labelledby="title description"
    >

        <title id="title">
            Estatísticas GitHub de Matheus Viana
        </title>

        <desc id="description">
            Estatísticas do perfil e tecnologias utilizadas
            nos projetos em que Matheus Viana contribui.
        </desc>

        <style>
            .background {{
                fill: #1a1b27;
                stroke: #30363d;
                stroke-width: 1;
            }}

            .title {{
                fill: #70a5fd;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;
                font-size: 22px;
                font-weight: 700;
            }}

            .subtitle {{
                fill: #8b949e;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;
                font-size: 12px;
            }}

            .stat-box {{
                fill: #161b22;
                stroke: #30363d;
                stroke-width: 1;
            }}

            .stat-label {{
                fill: #8b949e;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;
                font-size: 12px;
                font-weight: 500;
            }}

            .stat-value {{
                fill: #00e6c3;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;
                font-size: 22px;
                font-weight: 700;
            }}

            .section-title {{
                fill: #70a5fd;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;
                font-size: 16px;
                font-weight: 600;
            }}

            .language {{
                fill: #c9d1d9;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;
                font-size: 12px;
            }}

            .footer {{
                fill: #8b949e;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;
                font-size: 10px;
            }}

            .divider {{
                stroke: #30363d;
                stroke-width: 1;
            }}
        </style>

        <rect
            x="0.5"
            y="0.5"
            width="{CARD_WIDTH - 1}"
            height="{CARD_HEIGHT - 1}"
            rx="10"
            class="background"
        />

        <text
            x="28"
            y="34"
            class="title"
        >
            GitHub • Matheus Viana
        </text>

        <text
            x="28"
            y="55"
            class="subtitle"
        >
            Perfil pessoal + Projetos Profissionais
        </text>

        {''.join(stat_parts)}

        <line
            x1="28"
            y1="170"
            x2="{CARD_WIDTH - 28}"
            y2="170"
            class="divider"
        />

        <text
            x="28"
            y="197"
            class="section-title"
        >
            Tecnologias nos projetos em que contribuo
        </text>

        {''.join(bar_parts)}

        {''.join(legend_parts)}

        <text
            x="28"
            y="322"
            class="footer"
        >
            {escape(footer)}
        </text>

    </svg>"""

    return svg

def main():
    print(
        "Gerando estatísticas do perfil..."
    )

    contributions = (
        get_all_time_contributions()
    )

    print(
        "Consultando tecnologias dos projetos..."
    )

    technologies = (
        collect_technology_data()
    )

    print(
        "Projetos pessoais considerados: "
        f"{technologies['personal_projects']}"
    )

    print(
        "Projetos da organização considerados: "
        f"{technologies['organization_projects']}"
    )

    print(
        "Contribuições detectadas na organização: "
        f"{technologies['organization_contributions']}"
    )

    if not technologies["languages"]:
        raise RuntimeError(
            "Nenhuma linguagem foi encontrada."
        )

    svg = generate_svg(
        contributions,
        technologies,
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        svg,
        encoding="utf-8",
    )

    print(
        "Card gerado com sucesso em "
        "profile/github-stats.svg"
    )


if __name__ == "__main__":
    main()
