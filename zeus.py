#!/usr/bin/env python

import optparse
import os
import subprocess
import time

try:
    import http.client as http_client  # Python 3
except ImportError:
    import httplib as http_client  # Python 2

from var import blackwidow
from var.google_search import search
from var.auto_issue.github import request_issue_creation
from lib.attacks.admin_panel_finder import main
from lib.attacks.xss_scan import main_xss
from lib.attacks.nmap_scan.nmap_opts import NMAP_API_OPTS
from lib.attacks.sqlmap_scan.sqlmap_opts import SQLMAP_API_OPTIONS
from lib.attacks.whois_lookup.whois import whois_lookup_main

from lib.core.errors import (
    InvalidInputProvided,
    InvalidProxyType
)


from lib.attacks import (
    nmap_scan,
    sqlmap_scan,
    intel_me
)
from lib.core.settings import (
    setup,
    BANNER,
    start_up,
    shutdown,
    logger,
    set_color,
    get_latest_log_file,
    CURRENT_LOG_FILE_PATH,
    URL_LOG_PATH,
    replace_http,
    prompt,
    get_random_dork,
    update_zeus,
    VERSION_STRING,
    URL_REGEX, URL_QUERY_REGEX,
    NMAP_MAN_PAGE_URL,
    SQLMAP_MAN_PAGE_URL,
    get_true_url,
    fix_log_file,
    SPIDER_LOG_PATH,
    config_headers,
    config_search_engine,
    find_running_opts,
    create_arguments
)

if __name__ == "__main__":

    parser = optparse.OptionParser(usage="{} -d|l|s|b DORK|FILE|URL [ATTACKS] [S-E] [--OPTS]".format(
        os.path.basename(__file__)
    ))

    # mandatory options
    mandatory = optparse.OptionGroup(parser, "Mandatory Options",
                                     "These options have to be used in order for Zeus to run")
    mandatory.add_option("-d", "--dork", dest="dorkToUse", metavar="DORK",
                         help="Specify a singular Google dork to use for queries")
    mandatory.add_option("-l", "--dork-list", dest="dorkFileToUse", metavar="FILE-PATH",
                         help="Specify a file full of dorks to run through"),
    mandatory.add_option("-r", "--rand-dork", dest="useRandomDork", action="store_true",
                         help="Use a random dork from the etc/dorks.txt file to perform the scan")
    mandatory.add_option("-b", "--blackwidow", dest="spiderWebSite", metavar="URL",
                         help="Spider a single webpage for all available URL's")
    mandatory.add_option("-f", "--url-file", dest="fileToEnumerate", metavar="FILE-PATH",
                         help="Run an attack on URL's in a given file")

    # attack options
    attacks = optparse.OptionGroup(parser, "Attack arguments",
                                   "These arguments will give you the choice on how you want to check the websites")
    attacks.add_option("-s", "--sqli", dest="runSqliScan", action="store_true",
                       help="Run a Sqlmap SQLi scan on the discovered URL's")
    attacks.add_option("-p", "--port-scan", dest="runPortScan", action="store_true",
                       help="Run a Nmap port scan on the discovered URL's")
    attacks.add_option("-i", "--intel-check", dest="intelCheck", action="store_true",
                       help="Check if a URL's host is exploitable via Intel ME AMT (CVE-2017-5689)")
    attacks.add_option("-a", "--admin-panel", dest="adminPanelFinder", action="store_true",
                       help="Search for the websites admin panel")
    attacks.add_option("-x", "--xss-scan", dest="runXssScan", action="store_true",
                       help="Run an XSS scan on the found URL's")
    attacks.add_option("-w", "--whois-lookup", dest="performWhoisLookup", action="store_true",
                       help="Perform a WhoIs lookup on the provided domain")
    attacks.add_option("--show-readable", dest="showReadableOutput", action="store_true",
                       help="Show human readable output from the WhoIs lookup")
    attacks.add_option("--sqlmap-args", dest="sqlmapArguments", metavar="SQLMAP-ARGS",
                       help="Pass the arguments to send to the sqlmap API within quotes & "
                            "separated by a comma. IE 'dbms mysql, verbose 3, level 5'")
    attacks.add_option("--nmap-args", dest="nmapArguments", metavar="NMAP-ARGS",
                       help="Pass the arguments to send to the nmap API within quotes & "
                            "separated by a pipe. IE '-O|-p 445, 1080'")
    attacks.add_option("--show-sqlmap", dest="showSqlmapArguments", action="store_true",
                       help="Show the arguments that the sqlmap API understands")
    attacks.add_option("--show-nmap", dest="showNmapArgs", action="store_true",
                       help="Show the arguments that nmap understands")
    attacks.add_option("-P", "--show-possibles", dest="showAllConnections", action="store_true",
                       help="Show all connections made during the admin panel search")
    attacks.add_option("--tamper", dest="tamperXssPayloads", metavar="TAMPER-SCRIPT",
                       help="Send the XSS payloads through tampering before sending to the target")
    attacks.add_option("--run-ip-address", dest="runAgainstIpAddress", action="store_true",
                       help="Run the Intel ME AMT exploit against the found host IP address instead of the hostname")
    attacks.add_option("--thread", dest="threadPanels", action="store_true",
                       help=optparse.SUPPRESS_HELP)
    attacks.add_option("--auto", dest="autoStartSqlmap", action="store_true",
                       help=optparse.SUPPRESS_HELP)

    # search engine options
    engines = optparse.OptionGroup(parser, "Search engine arguments",
                                   "Arguments to change the search engine used (default is Google)")
    engines.add_option("-D", "--search-engine-ddg", dest="useDDG", action="store_true",
                       help="Use DuckDuckGo as the search engine")
    engines.add_option("-B", "--search-engine-bing", dest="useBing", action="store_true",
                       help="Use Bing as the search engine")
    engines.add_option("-A", "--search-engine-aol", dest="useAOL", action="store_true",
                       help="Use AOL as the search engine")

    # arguments to edit your search patterns
    search_items = optparse.OptionGroup(parser, "Search options",
                                        "Arguments that will control the search criteria")
    search_items.add_option("-L", "--links", dest="amountToSearch", type=int, metavar="HOW-MANY-LINKS",
                            help="Specify how many links to try and search on Google")
    search_items.add_option("-M", "--multi", dest="searchMultiplePages", action="store_true",
                            help="Search multiple pages of Google")
    search_items.add_option("-E", "--exclude-none", dest="noExclude", action="store_true",
                            help="Do not exclude URLs because they do not have a GET(query) parameter in them")
    search_items.add_option("-W", "--webcache", dest="parseWebcache", action="store_true",
                            help="Parse webcache URLs for the redirect in them")

    # obfuscation options
    anon = optparse.OptionGroup(parser, "Anonymity arguments",
                                "Arguments that help with anonymity and hiding identity")
    anon.add_option("--proxy", dest="proxyConfig", metavar="PROXY-STRING",
                    help="Use a proxy to do the scraping, will not auto configure to the API's")
    anon.add_option("--proxy-file", dest="proxyFileRand", metavar="FILE-PATH",
                    help="Grab a random proxy from a given file of proxies")
    anon.add_option("--random-agent", dest="useRandomAgent", action="store_true",
                    help="Use a random user-agent from the etc/agents.txt file")
    anon.add_option("--agent", dest="usePersonalAgent", metavar="USER-AGENT",
                    help="Use your own personal user-agent")

    # miscellaneous options
    misc = optparse.OptionGroup(parser, "Misc Options",
                                "These options affect how the program will run")
    misc.add_option("--verbose", dest="runInVerbose", action="store_true",
                    help="Run the application in verbose mode (more output)")
    misc.add_option("--show-requests", dest="showRequestInfo", action="store_true",
                    help="Show all HTTP requests made by the application")
    misc.add_option("--batch", dest="runInBatch", action="store_true",
                    help="Skip the questions and run in default batch mode")
    misc.add_option("--update", dest="updateZeus", action="store_true",
                    help="Update to the latest development version")
    misc.add_option("--hide", dest="hideBanner", action="store_true",
                    help="Hide the banner during running")
    misc.add_option("--version", dest="showCurrentVersion", action="store_true",
                    help="Show the current version and exit")

    parser.add_option_group(mandatory)
    parser.add_option_group(attacks)
    parser.add_option_group(search_items)
    parser.add_option_group(anon)
    parser.add_option_group(engines)
    parser.add_option_group(misc)

    opt, _ = parser.parse_args()

    if opt.showCurrentVersion:
        print(VERSION_STRING)
        exit(0)

    # run the setup on the program
    setup(verbose=opt.runInVerbose)

    if not opt.hideBanner:
        print(BANNER)

    start_up()

    if opt.showSqlmapArguments:
        logger.info(set_color(
            "there are a total of {} arguments understood by sqlmap API, "
            "they include:".format(len(SQLMAP_API_OPTIONS))
        ))
        print("\n")
        for arg in SQLMAP_API_OPTIONS:
            print(
                "[*] {}".format(arg)
            )
        print("\n")
        logger.info(set_color(
            "for more information about sqlmap arguments, see here '{}'...".format(
                SQLMAP_MAN_PAGE_URL
            )
        ))
        shutdown()

    if opt.showNmapArgs:
        logger.info(set_color(
            "there are a total of {} arguments understood by nmap, they include:".format(
                len(NMAP_API_OPTS)
            )
        ))
        print("\n")
        for arg in NMAP_API_OPTS:
            print(
                "[*] {}".format(arg)
            )
        print("\n")
        logger.info(set_color(
            "for more information on what the arguments do please see here '{}'...".format(
                NMAP_MAN_PAGE_URL
            )
        ))
        shutdown()

    # update the program
    if opt.updateZeus:
        logger.info(set_color(
            "update in progress..."
        ))
        update_zeus()
        shutdown()

    if opt.runInVerbose:
        being_run = find_running_opts(opt)
        logger.debug(set_color(
            "running with options '{}'...".format(being_run), level=10
        ))

    logger.info(set_color(
        "log file being saved to '{}'...".format(get_latest_log_file(CURRENT_LOG_FILE_PATH))
    ))

    if opt.showRequestInfo:
        logger.debug(set_color(
            "showing all HTTP requests because --show-requests flag was used...", level=10
        ))
        http_client.HTTPConnection.debuglevel = 1

    def __choose_attack(choice, attacks):
        while True:
            if int(choice) in range(len(attacks)):
                return int(choice)
            else:
                logger.warning(set_color(
                    "{} is not a valid choice...".format(choice)
                ))


    def __run_attacks(url, **kwargs):
        """
        run the attacks if any are requested
        """
        nmap = kwargs.get("nmap", False)
        sqlmap = kwargs.get("sqlmap", False)
        intel = kwargs.get("intel", False)
        xss = kwargs.get("xss", False)
        admin = kwargs.get("admin", False)
        verbose = kwargs.get("verbose", False)
        whois = kwargs.get("whois", False)
        batch = kwargs.get("batch", False)
        auto_start = kwargs.get("auto_start", False)

        __enabled_attacks = {
            "sqlmap": opt.runSqliScan,
            "port": opt.runPortScan,
            "xss": opt.runXssScan,
            "admin": opt.adminPanelFinder,
            "intel": opt.intelCheck,
            "whois": opt.performWhoisLookup
        }

        enabled = set()
        for key in __enabled_attacks.keys():
            if __enabled_attacks[key] is True:
                enabled.add(key)
            if len(enabled) > 1:
                logger.error(set_color(
                    "it appears that you have enabled multiple attack types, "
                    "as of now only 1 attack is supported at a time, choose "
                    "your attack and try again. You can use the -f flag if "
                    "you do not want to complete an entire search again "
                    "(IE -f /home/me/zeus-scanner/log/url-log/url-log-1.log)...", level=40
                ))
                shutdown()

        if not batch:
            question = prompt(
                "would you like to process found URL: '{}'".format(url), opts=["y", "N"]
            )
        else:
            question = "y"

        if question.lower().startswith("y"):
            if sqlmap:
                return sqlmap_scan.sqlmap_scan_main(
                    url.strip(), verbose=verbose,
                    opts=create_arguments(sqlmap=True, sqlmap_args=opt.sqlmapArguments), auto_start=auto_start)
            elif nmap:
                url_ip_address = replace_http(url.strip())
                return nmap_scan.perform_port_scan(
                    url_ip_address, verbose=verbose,
                    opts=create_arguments(nmap=True, nmap_args=opt.nmapArguments)
                )
            elif intel:
                url = get_true_url(url)
                return intel_me.main_intel_amt(
                    url, agent=agent_to_use,
                    proxy=proxy_to_use, do_ip=opt.runAgainstIpAddress
                )
            elif admin:
                main(
                    url, show=opt.showAllConnections,
                    verbose=verbose, do_threading=opt.threadPanels
                )
            elif xss:
                main_xss(
                    url, verbose=verbose, proxy=proxy_to_use,
                    agent=agent_to_use, tamper=opt.tamperXssPayloads
                )
            elif whois:
                whois_lookup_main(
                    url, verbose=opt.runInVerbose, readable=opt.showReadableOutput
                )
            else:
                pass
        else:
            logger.warning(set_color(
                "skipping '{}'...".format(url), level=30
            ))


    def __run_attacks_main():
        """
        main method to run the attacks
        """
        which_log_to_use = {
            "dork": URL_LOG_PATH,
            "spider": SPIDER_LOG_PATH
        }

        options = (opt.useRandomDork, opt.dorkToUse, opt.dorkFileToUse, opt.fileToEnumerate)
        to_use = which_log_to_use["dork"] if any(arg for arg in options) is True else which_log_to_use["spider"]
        try:
            urls_to_use = get_latest_log_file(to_use)
        except TypeError:
            urls_to_use = None

        if urls_to_use is None:
            logger.error(set_color(
                "unable to run attacks appears that no file was created for the retrieved data...", level=40
            ))
            shutdown()
        options = [
            opt.runSqliScan, opt.runPortScan,
            opt.intelCheck, opt.adminPanelFinder,
            opt.runXssScan, opt.performWhoisLookup
        ]
        if any(options):
            with open(urls_to_use) as urls:
                for url in urls.readlines():
                    __run_attacks(
                        url.strip(),
                        sqlmap=opt.runSqliScan, nmap=opt.runPortScan,
                        intel=opt.intelCheck, xss=opt.runXssScan,
                        whois=opt.performWhoisLookup, admin=opt.adminPanelFinder,
                        verbose=opt.runInVerbose, batch=opt.runInBatch,
                        auto_start=opt.autoStartSqlmap
                    )


    proxy_to_use, agent_to_use = config_headers(
        proxy=opt.proxyConfig, proxy_file=opt.proxyFileRand,
        p_agent=opt.usePersonalAgent, rand_agent=opt.useRandomAgent,
        verbose=opt.runInVerbose
    )
    search_engine = config_search_engine(
        verbose=opt.runInVerbose, ddg=opt.useDDG,
        aol=opt.useAOL, bing=opt.useBing, enum=opt.fileToEnumerate
    )

    try:
        # use a personal dork as the query
        if opt.dorkToUse is not None and not opt.searchMultiplePages:
            logger.info(set_color(
                "starting dork scan with query '{}'...".format(opt.dorkToUse)
            ))
            try:
                search.parse_search_results(
                    opt.dorkToUse, search_engine, verbose=opt.runInVerbose, proxy=proxy_to_use,
                    agent=agent_to_use, pull_all=opt.noExclude, parse_webcache=opt.parseWebcache
                )
            except InvalidProxyType:
                supported_proxy_types = ["socks5", "socks4", "https", "http"]
                logger.fatal(set_color(
                    "the provided proxy is not valid, specify the protocol and try again, supported "
                    "proxy protocols are {} (IE socks5://127.0.0.1:9050)...".format(", ".join(supported_proxy_types)), level=50
                ))
            except Exception as e:
                logger.exception(set_color(
                    "ran into exception '{}'...".format(e), level=50
                ))
                request_issue_creation()
                pass

            __run_attacks_main()

        # search multiple pages of Google
        elif opt.dorkToUse is not None and opt.searchMultiplePages:
            if opt.amountToSearch is None:
                logger.fatal(set_color(
                    "did not specify amount of links to find...", level=50
                ))
                shutdown()
            link_amount_to_search = opt.amountToSearch
            logger.info(set_color(
                "searching Google using dork '{}' for a total of {} links...".format(opt.dorkToUse, opt.amountToSearch)
            ))
            try:
                search.search_multiple_pages(opt.dorkToUse, link_amount_to_search, proxy=proxy_to_use,
                                             agent=agent_to_use, verbose=opt.runInVerbose)
            except Exception as e:
                if "Error 400" in str(e):
                    logger.fatal(set_color(
                        "failed to connect to search engine...".format(e), level=50
                    ))
                elif "Error 503" in str(e):
                    logger.fatal(set_color(
                        "Google has blocked your IP address from doing anymore searches via API, "
                        "you can still search using headless browsers (-d <DORK>)...", level=50
                    ))
                else:
                    logger.exception(set_color(
                        "failed with unexpected error '{}'...".format(e), level=50
                    ))
                shutdown()

            __run_attacks_main()

        # use a file full of dorks as the queries
        elif opt.dorkFileToUse is not None:
            with open(opt.dorkFileToUse) as dorks:
                for dork in dorks.readlines():
                    dork = dork.strip()
                    logger.info(set_color(
                        "starting dork scan with query '{}'...".format(dork)
                    ))
                    try:
                        search.parse_search_results(
                            dork, search_engine, verbose=opt.runInVerbose, proxy=proxy_to_use,
                            agent=agent_to_use, pull_all=opt.noExclude, parse_webcache=opt.parseWebcache
                        )
                    except Exception as e:
                        logger.exception(set_color(
                            "ran into exception '{}'...".format(e), level=50
                        ))
                        request_issue_creation()
                        pass

            __run_attacks_main()

        # use a random dork as the query
        elif opt.useRandomDork:
            random_dork = get_random_dork().strip()
            if opt.runInVerbose:
                logger.debug(set_color(
                    "choosing random dork from etc/dorks.txt...", level=10
                ))
            logger.info(set_color(
                "using random dork '{}' as the search query...".format(random_dork)
            ))
            try:
                search.parse_search_results(
                    random_dork, search_engine, verbose=opt.runInVerbose,
                    proxy=proxy_to_use, agent=agent_to_use, pull_all=opt.noExclude, parse_webcache=opt.parseWebcache
                )
                __run_attacks_main()

            except Exception as e:
                logger.exception(set_color(
                    "ran into exception '{}' and cannot continue, saved to current log file...".format(e),
                    level=50
                ))
                request_issue_creation()
                pass

        # spider a given webpage for all available URL's
        elif opt.spiderWebSite:
            problem_identifiers = ["http://", "https://"]
            if not URL_REGEX.match(opt.spiderWebSite):
                err_msg = "URL did not match a true URL{}..."
                if not any(m in opt.spiderWebSite for m in problem_identifiers):
                    err_msg = err_msg.format(" issue seems to be that http:// "
                                             "or https:// is not present in the URL")
                else:
                    err_msg = err_msg.format("")
                raise InvalidInputProvided(
                    err_msg
                )
            else:
                if URL_QUERY_REGEX.match(opt.spiderWebSite):
                    is_sure = prompt(
                        "it is recomened to not use a URL that has a GET(query) parameter in it, "
                        "would you like to continue", "yN"
                    )
                    if is_sure.lower().startswith("y"):
                        pass
                    else:
                        shutdown()

            blackwidow.blackwidow_main(opt.spiderWebSite, agent=agent_to_use, proxy=proxy_to_use,
                                       verbose=opt.runInVerbose)

            __run_attacks_main()

        # enumerate a file and run attacks on the URL's provided
        elif opt.fileToEnumerate is not None:
            __run_attacks_main()

        else:
            logger.critical(set_color(
                "failed to provide a mandatory argument, you will be redirected to the help menu...", level=50
            ))
            time.sleep(2)
            subprocess.call("python zeus.py --help", shell=True)
    except IOError as e:
        if "Invalid URL" in str(e):
            logger.exception(set_color(
                "URL provided is not valid, schema appears to be missing...", level=50
            ))
            request_issue_creation()
            shutdown()
        else:
            logger.fatal(set_color(
                "provided file does not exist, make sure you have the full path...", level=50
            ))
    except KeyboardInterrupt:
        logger.error(set_color(
            "user aborted process...", level=40
        ))
    except UnboundLocalError:
        logger.warning(set_color(
            "do not interrupt the browser when selenium is running, "
            "it will cause Zeus to crash...", level=30
        ))
    except Exception as e:
        if "url did not match a true url" in str(e).lower():
            logger.error(set_color(
                "you did not provide a URL that is capable of being processed, "
                "the URL provided to the spider needs to contain protocol as well "
                "ie. 'http://google.com' (it is advised not to add the GET parameter), "
                "fix the URL you want to scan and try again...", level=40
            ))
            shutdown()
        elif "Service geckodriver unexpectedly exited" in str(e):
            logger.fatal(set_color(
                "it seems that your firefox version is not compatible with the geckodriver "
                "version. please update firefox and try again...", level=50
            ))
            shutdown()
        elif "Max retries exceeded with url" in str(e):
            logger.fatal(set_color(
                "you have hit the max retries, to continue using Zeus "
                "it is recommended to use a proxy (--proxy/--proxy-file) "
                "along with a new user-agent (--random-agent/--agent).", level=50
            ))
            shutdown()
        else:
            logger.exception(set_color(
                "ran into exception '{}' exception has been saved to log file...".format(e), level=50
            ))
            request_issue_creation()

    # fix the log file before shutting down incase you want to look at it
    fix_log_file()
shutdown()