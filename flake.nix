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

    flake-utils.url = "github:numtide/flake-utils";

    git-hooks-nix = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  # ----------------------------------------------------------------------------
  # Outputs
  # ----------------------------------------------------------------------------
  outputs =
    {
      nixpkgs,
      flake-utils,
      git-hooks-nix,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
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
            cmdLineToolsVersion = "20.0";
            toolsVersion = null;
            platformToolsVersion = "37.0.0";
            buildToolsVersions = [ "36.0.0" ];
            platformVersions = [ "36" ];
            includeEmulator = true;
            emulatorVersion = "36.5.11";
            includeSystemImages = true;
            systemImageTypes = [ "default" ];
            abiVersions = [
              (if pkgs.stdenv.hostPlatform.isAarch64 then "arm64-v8a" else "x86_64")
            ];
            includeCmake = false;
          }).androidsdk;

        # ----------------------------------------------------------------------
        # Pre-commit hooks
        # ----------------------------------------------------------------------
        preCommitCheck = git-hooks-nix.lib.${system}.run {
          src = ./.;
          package = pkgs.prek;
          hooks = {
            check-added-large-files.enable = true;

            check-yaml.enable = true;

            cspell = {
              enable = true;
              args = [
                "--no-progress"
                "--no-must-find-files"
              ];
            };

            deadnix.enable = true;

            end-of-file-fixer.enable = true;

            markdownlint-cli2 = {
              enable = true;
              entry = "${pkgs.markdownlint-cli2}/bin/markdownlint-cli2";
              files = "\\.md$";
            };

            nixfmt.enable = true;

            statix.enable = true;

            trim-trailing-whitespace = {
              enable = true;
              args = [ "--markdown-linebreak-ext=md" ];
            };
          };
        };
      in
      {
        checks.pre-commit = preCommitCheck;

        devShells = {
          python = pkgs.mkShell pythonEnvironment;

          default = pkgs.mkShell (
            pythonEnvironment
            // {
              packages =
                pythonEnvironment.packages
                ++ preCommitCheck.enabledPackages
                ++ (with pkgs; [
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
                ]);

              inherit (preCommitCheck) shellHook;
            }
          );
        }
        //
          pkgs.lib.optionalAttrs
            (pkgs.lib.elem system [
              "aarch64-darwin"
              "x86_64-darwin"
              "x86_64-linux"
            ])
            {
              android = pkgs.mkShell {
                packages = [
                  androidSdk
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
                '';
              };
            };

        formatter = pkgs.nixfmt-tree;
      }
    );
}
