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

        devShells.default = pkgs.mkShell {
          packages =
            preCommitCheck.enabledPackages
            ++ (with pkgs; [
              apktool
              binutils
              curl
              file
              git
              jadx
              jq
              python314
              ripgrep
              unzip
              uv
              zsh
            ]);

          inherit (preCommitCheck) shellHook;
          UV_PYTHON_DOWNLOADS = "never";
        };

        formatter = pkgs.nixfmt-tree;
      }
    );
}
