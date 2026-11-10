class Codegraph < Formula
  include Language::Python::Virtualenv

  desc "Deterministic, local-first code graph engine and MCP server"
  homepage "https://pypi.org/project/codegraph-engine/3.0.1/"
  url "https://files.pythonhosted.org/packages/89/94/b6159edcc3018ede7e429e056da573596e3ccd64903d66ff9103fb5c4480/codegraph_engine-3.0.1.tar.gz"
  sha256 "46b60f0d1f8546760b8e38d14e6eb0a4367be46248d64905a5efaaa0dbad8acb"
  version "3.0.1"
  license "Apache-2.0"

  depends_on "python@3.12"

  def install
    virtualenv_create(libexec, "python3.12")
    system libexec/"bin/pip", "install", "--no-cache-dir", buildpath
    bin.install_symlink libexec/"bin/codegraph"
  end

  test do
    system "#{bin}/codegraph", "--version"
  end
end
