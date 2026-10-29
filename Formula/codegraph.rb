class Codegraph < Formula
  include Language::Python::Virtualenv

  desc "Deterministic, local-first code graph engine and MCP server"
  homepage "https://pypi.org/project/codegraph-engine/3.0.1/"
  url "https://files.pythonhosted.org/packages/source/c/codegraph-engine/codegraph_engine-3.0.1.tar.gz"
  version "3.0.1"
  license "Apache-2.0"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/codegraph", "--version"
  end
end
