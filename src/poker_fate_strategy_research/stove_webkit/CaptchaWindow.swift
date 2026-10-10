import AppKit
import Foundation
import WebKit

@MainActor
final class CaptchaWindow: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    private let localURL = URL(string: Bundle.main.object(forInfoDictionaryKey: "ResearchOrigin") as! String)!
    private var csrf = ""
    private var received = false
    private var preparing = false
    private var checking = false
    private var statusTimer: Timer?
    private var webView: WKWebView!
    private var window: NSWindow!
    private let session: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil
        configuration.httpCookieStorage = nil
        return URLSession(configuration: configuration)
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.userContentController.add(self, name: "captcha")
        configuration.userContentController.add(self, name: "closed")
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 680, height: 720),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false
        )
        window.title = "STOVE Verification"
        window.contentView = webView
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        webView.load(URLRequest(url: localURL))
        statusTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.checkStatus()
            }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationWillTerminate(_ notification: Notification) {
        statusTimer?.invalidate()
    }

    private func show(_ message: String) {
        webView.loadHTMLString(
            "<html lang='en'><meta charset='utf-8'><style>body{font:18px system-ui;margin:40px;line-height:1.6}</style><h1>STOVE Verification</h1><p>\(message)</p></html>",
            baseURL: nil
        )
    }

    private func prepare() async {
        guard !preparing else { return }
        preparing = true
        defer { preparing = false }
        received = false
        webView.configuration.userContentController.removeAllUserScripts()
        do {
            let (data, response) = try await session.data(from: localURL.appendingPathComponent("challenge-info"))
            guard (response as? HTTPURLResponse)?.statusCode == 200,
                  let info = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let challengeURLString = info["url"] as? String,
                  let challengeURL = URL(string: challengeURLString),
                  challengeURL.scheme == "https", challengeURL.host == "accounts.onstove.com",
                  challengeURL.path == "/auth/captcha",
                  let nonce = info["csrf"] as? String,
                  let values = info["values"], let device = info["device"],
                  let sourceURL = Bundle.main.url(forResource: "challenge_bridge", withExtension: "js")
            else {
                show("Cannot load the verification configuration.")
                return
            }
            csrf = nonce
            let bridgeData = try JSONSerialization.data(withJSONObject: ["values": values, "device": device])
            let bridgeJSON = String(decoding: bridgeData, as: UTF8.self)
            let source = try String(contentsOf: sourceURL, encoding: .utf8)
                .replacingOccurrences(of: "__LOCAL_CHALLENGE_INFO__", with: bridgeJSON)
            let callbacks = """
            window.localResearchCaptchaResult = value => window.webkit.messageHandlers.captcha.postMessage(value);
            window.localResearchCaptchaClosed = value => window.webkit.messageHandlers.closed.postMessage(value);
            """
            webView.configuration.userContentController.addUserScript(
                WKUserScript(source: callbacks + "\n" + source, injectionTime: .atDocumentStart, forMainFrameOnly: true)
            )
            webView.load(URLRequest(url: challengeURL))
        } catch {
            show("Cannot connect to the local sign-in service.")
            print("Verification configuration failed: \(type(of: error)).")
        }
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame,
              message.frameInfo.securityOrigin.protocol == "https",
              message.frameInfo.securityOrigin.host == "accounts.onstove.com"
        else { return }
        if message.name == "closed" {
            show("Verification was cancelled.")
            return
        }
        guard message.name == "captcha", !received,
              let token = message.body as? String, !token.isEmpty, token.utf8.count <= 12000
        else { return }
        received = true
        Task {
            await deliver(token)
        }
    }

    private func deliver(_ token: String) async {
        do {
            var request = URLRequest(url: localURL.appendingPathComponent("captcha-token"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(localURL.absoluteString, forHTTPHeaderField: "Origin")
            request.httpBody = try JSONSerialization.data(withJSONObject: ["csrf": csrf, "token": token])
            let (_, response) = try await session.data(for: request)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else {
                show("The local sign-in service did not accept the verification result.")
                return
            }
            csrf = ""
            webView.configuration.userContentController.removeAllUserScripts()
            webView.load(URLRequest(url: localURL))
            print("STOVE verification delivered. Sign-in continued using saved credentials.")
        } catch {
            show("Cannot deliver the verification result to the local sign-in service.")
            print("Verification delivery failed: \(type(of: error)).")
        }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        Task {
            await checkStatus()
        }
    }

    private func checkStatus() async {
        guard !checking else { return }
        guard let url = webView.url,
              url.scheme == localURL.scheme, url.host == localURL.host,
              url.port == localURL.port, url.path == "/" || url.path.isEmpty
        else { return }
        checking = true
        defer { checking = false }
        do {
            let (data, response) = try await session.data(from: localURL.appendingPathComponent("status"))
            guard (response as? HTTPURLResponse)?.statusCode == 200,
                  let status = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { return }
            if status["phase"] as? String == "captcha" {
                await prepare()
            }
        } catch {
            show("Cannot read the local sign-in status.")
        }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        navigationFailed(error)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        navigationFailed(error)
    }

    private func navigationFailed(_ error: Error) {
        let failure = error as NSError
        if failure.domain == NSURLErrorDomain && failure.code == NSURLErrorCancelled {
            return
        }
        show("Cannot load the page (error \(failure.code)).")
        print("Sign-in navigation failed: \(failure.domain), code \(failure.code).")
    }
}

@main
enum VerificationApplication {
    @MainActor
    static func main() {
        let application = NSApplication.shared
        let delegate = CaptchaWindow()
        application.delegate = delegate
        application.setActivationPolicy(.regular)
        let menu = NSMenu()
        let item = NSMenuItem()
        menu.addItem(item)
        let applicationMenu = NSMenu()
        applicationMenu.addItem(withTitle: "Quit STOVE Verification", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.submenu = applicationMenu
        application.mainMenu = menu
        application.run()
    }
}
