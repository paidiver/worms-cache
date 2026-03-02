# frozen_string_literal: true

require 'taxamatch_rb'
require_relative 'utils'

class TaxamatchService
  def initialize
    @tm = Taxamatch::Base.new
    @atomizer = Taxamatch::Atomizer.new
  end

  def match_one(input:, candidates:)
    input = input.to_s.strip
    entry = { matched_ids: [], errors: [], mode: nil }

    if input.empty?
      entry[:errors] << 'empty query'
      return entry
    end

    if Utils.token_count(input) == 1
      entry[:mode] = 'single_token'
      match_single_token(entry, input, candidates)
    else
      entry[:mode] = 'full_taxamatch'
      match_full(entry, input, candidates)
    end

    entry
  end

  private

  def match_single_token(entry, input, candidates)
    candidates.each do |c|
      cid = c['id']
      name = c['name'].to_s.strip
      next if name.empty?

      parts = name.split(/\s+/)
      cand_genus   = parts[0].to_s.strip
      cand_species = parts[1].to_s.strip

      ok_genus = false
      ok_species = false

      begin
        unless cand_genus.empty?
          input_genus_str = input.capitalize
          cand_genus_str  = cand_genus.capitalize

          res = @tm.match_genera(
            Utils.make_taxamatch_hash(input_genus_str),
            Utils.make_taxamatch_hash(cand_genus_str)
          )

          ok_genus = res && res['match']
        end

        species_token = cand_species.empty? ? cand_genus : cand_species
        unless species_token.empty?
          input_species_str = input.downcase
          cand_species_str  = species_token.downcase

          res = @tm.match_species(
            Utils.make_taxamatch_hash(input_species_str),
            Utils.make_taxamatch_hash(cand_species_str)
          )

          ok_species = res && res['match']
        end

        entry[:matched_ids] << cid if ok_genus || ok_species
      rescue StandardError => e
        entry[:errors] << "single_token error for id=#{cid}: #{e.class}"
      end
    end
  end

  def match_full(entry, input, candidates)
    input_parsed =
      begin
        @atomizer.parse(input)
      rescue StandardError => e
        entry[:errors] << "atomizer parse error for query: #{e.class}"
        nil
      end

    candidates.each do |c|
      cid = c['id']
      name = c['name'].to_s.strip
      next if name.empty?

      cand_parsed = @atomizer.parse(name)

      ok =
        if input_parsed && cand_parsed
          res = @tm.taxamatch_preparsed(input_parsed, cand_parsed)
          res && res['match']
        else
          @tm.taxamatch(input, name)
        end

      entry[:matched_ids] << cid if ok
    rescue StandardError => e
      entry[:errors] << "taxamatch error for id=#{cid}: #{e.class}"
    end
  end
end
