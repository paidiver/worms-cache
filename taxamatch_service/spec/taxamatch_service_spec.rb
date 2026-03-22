# frozen_string_literal: true

require 'spec_helper'

RSpec.describe TaxamatchService do
  let(:service) { described_class.new }

  describe '#match_one' do
    context 'when input is single token' do
      it 'matches genus when candidate has one token (capitalization-insensitive)' do
        input = 'homo'
        candidates = [
          { 'id' => 1, 'name' => 'Homo' },
          { 'id' => 2, 'name' => 'Pan' }
        ]

        res = service.match_one(input: input, candidates: candidates)

        expect(res[:mode]).to eq('single_token')
        expect(res[:matched_ids]).to include(1)
        expect(res[:matched_ids]).not_to include(2)
        expect(res[:errors]).to be_empty
      end

      it 'matches species when candidate has one token (lowercasing for species compare)' do
        input = 'Sapiens'
        candidates = [
          { 'id' => 1, 'name' => 'sapiens' },
          { 'id' => 2, 'name' => 'erectus' }
        ]

        res = service.match_one(input: input, candidates: candidates)

        expect(res[:mode]).to eq('single_token')
        expect(res[:matched_ids]).to include(1)
        expect(res[:matched_ids]).not_to include(2)
        expect(res[:errors]).to be_empty
      end

      it 'also checks species token when candidate has two tokens' do
        input = 'sapiens'
        candidates = [
          { 'id' => 1, 'name' => 'Homo sapiens' },
          { 'id' => 2, 'name' => 'Homo erectus' }
        ]

        res = service.match_one(input: input, candidates: candidates)

        expect(res[:mode]).to eq('single_token')
        expect(res[:matched_ids]).to include(1)
        expect(res[:matched_ids]).not_to include(2)
      end

      it 'does not crash on empty candidate names' do
        input = 'homo'
        candidates = [
          { 'id' => 1, 'name' => '' },
          { 'id' => 2, 'name' => '   ' },
          { 'id' => 3, 'name' => 'Homo' }
        ]

        res = service.match_one(input: input, candidates: candidates)

        expect(res[:matched_ids]).to include(3)
        expect(res[:errors]).to be_empty
      end
    end

    context 'when input has multiple tokens' do
      it 'uses full_taxamatch mode and matches identical names' do
        input = 'Homo sapiens'
        candidates = [
          { 'id' => 1, 'name' => 'Homo sapiens' },
          { 'id' => 2, 'name' => 'Pan troglodytes' }
        ]

        res = service.match_one(input: input, candidates: candidates)

        expect(res[:mode]).to eq('full_taxamatch')
        expect(res[:matched_ids]).to include(1)
        expect(res[:matched_ids]).not_to include(2)
      end
    end
  end
end
