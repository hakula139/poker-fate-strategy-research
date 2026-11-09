# ==============================================================================
# Poker Fate Strategy Research Development Flake
# ==============================================================================

{
  description = "Poker Fate strategy research environment";

  # ----------------------------------------------------------------------------
  # Inputs
  # ----------------------------------------------------------------------------
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

    devkit = {
      url = "github:hakula139/devkit/v2";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  # ----------------------------------------------------------------------------
  # Outputs
  # ----------------------------------------------------------------------------
  outputs =
    {
      nixpkgs,
      devkit,
      ...
    }:
    devkit.lib.eachSystem
      [
        "aarch64-darwin"
        "x86_64-linux"
      ]
      (
        system:
        let
          pkgs = import nixpkgs { inherit system; };

          # ----------------------------------------------------------------------
          # Python environment
          # ----------------------------------------------------------------------
          pythonEnvironment = {
            packages = with pkgs; [
              mitmproxy
              protobuf
              python313
              uv
            ];

            UV_PYTHON_DOWNLOADS = "never";
          };

          # ----------------------------------------------------------------------
          # Android environment
          # ----------------------------------------------------------------------
          androidPkgs = import nixpkgs {
            inherit system;
            config = {
              android_sdk.accept_license = true;
              allowUnfreePredicate = pkg: (pkg.meta.homepage or "") == "https://developer.android.com/tools";
            };
          };

          androidSdk =
            (androidPkgs.androidenv.composeAndroidPackages {
              abiVersions = [
                (if pkgs.stdenv.hostPlatform.isAarch64 then "arm64-v8a" else "x86_64")
              ];
              buildToolsVersions = [ "36.0.0" ];
              cmdLineToolsVersion = "20.0";
              emulatorVersion = "36.5.11";
              includeCmake = false;
              includeEmulator = true;
              includeSystemImages = true;
              platformToolsVersion = "37.0.0";
              platformVersions = [ "36" ];
              systemImageTypes = [ "default" ];
              toolsVersion = null;
            }).androidsdk;

          # ----------------------------------------------------------------------
          # Frida environment
          # ----------------------------------------------------------------------
          fridaPython =
            let
              wheel = {
                aarch64-darwin = {
                  hash = "sha256-UaY7owWhEuzuHSGkaphwAfr7vM/M91qBZy3nBpu+iRc=";
                  platform = "macosx_11_0_arm64";
                };
                x86_64-linux = {
                  hash = "sha256-6e1VVdFfpajcFon7ghb+x63hpA/3vV1YOMJqPvCX7Ec=";
                  platform = "manylinux1_x86_64";
                };
              };
            in
            pkgs.python3Packages.frida-python.overridePythonAttrs rec {
              version = "17.23.3";
              src = pkgs.fetchPypi {
                pname = "frida";
                inherit version;
                abi = "abi3";
                dist = "cp37";
                format = "wheel";
                inherit (wheel.${system}) hash platform;
                python = "cp37";
              };
            };

          fridaTools = pkgs.frida-tools.override {
            python3Packages = pkgs.python3Packages // {
              frida-python = fridaPython;
            };
          };

          # ----------------------------------------------------------------------
          # Pre-commit hooks
          # ----------------------------------------------------------------------
          preCommit = (devkit.lib.mkLib pkgs).preCommit {
            src = ./.;
            hooks = {
              actionlint.enable = true;
              check-yaml.enable = true;
              cspell.enable = true;
              deadnix.enable = true;
              dprint.enable = true;
              markdownlint-cli2.enable = true;
              nixfmt.enable = true;
              prettier.enable = true;
              ruff.enable = true;
              ruff-format.enable = true;
              shellcheck.enable = true;
              shfmt.enable = true;
              sort-file-contents.enable = true;
              statix.enable = true;
              taplo.enable = true;
            };
          };

        in
        {
          checks.pre-commit = preCommit.check;

          devShells = {
            android = pkgs.mkShell {
              packages = [
                androidSdk
                fridaTools
                pkgs.jdk17
              ];

              ANDROID_HOME = "${androidSdk}/libexec/android-sdk";
              ANDROID_SDK_ROOT = "${androidSdk}/libexec/android-sdk";
              JAVA_HOME = "${pkgs.jdk17.home}";

              shellHook = ''
                export ANDROID_USER_HOME="$PWD/work/android-runtime"
                export ANDROID_EMULATOR_HOME="$ANDROID_USER_HOME"
                export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"
                mkdir -p "$ANDROID_AVD_HOME"
                chmod 700 "$ANDROID_USER_HOME" "$ANDROID_AVD_HOME"
              '';
            };

            python = pkgs.mkShell pythonEnvironment;

            default = pkgs.mkShell {
              inherit (pythonEnvironment) UV_PYTHON_DOWNLOADS;

              packages = with pkgs; [
                apktool
                binutils
                curl
                dotnet-runtime_8
                file
                git
                jadx
                jq
                ripgrep
                unzip
                zsh
              ];

              inputsFrom = [
                (pkgs.mkShell pythonEnvironment)
                preCommit.shell
              ];
            };
          };

          formatter = pkgs.nixfmt-tree;
        }
      );
}
