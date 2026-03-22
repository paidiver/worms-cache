# frozen_string_literal: true

module Utils
  module_function

  def token_count(s)
    s.to_s.strip.split(/\s+/).length
  end

  def make_taxamatch_hash(str)
    s = str.to_s.strip
    normalized = Taxamatch::Normalizer.normalize(s)
    {
      string: s,
      normalized: normalized,
      phonetized: Taxamatch::Phonetizer.near_match(normalized)
    }
  end
end
