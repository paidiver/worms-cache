# frozen_string_literal: true

require 'sinatra'
require 'json'
require_relative 'lib/taxamatch_service'

$stdout.sync = true

set :bind, ENV.fetch('BIND', '0.0.0.0')
set :port, ENV.fetch('PORT', '8080').to_i
set :environment, ENV.fetch('RACK_ENV', 'production').to_sym

MAX_NAMES = (ENV['MAX_NAMES'] || '50').to_i
MAX_CANDIDATES_PER_NAME = (ENV['MAX_CANDIDATES_PER_NAME'] || '300').to_i

before { content_type :json }

SERVICE = TaxamatchService.new

get '/health' do
  status 200
  { ok: true, version: Taxamatch.version }.to_json
end

post '/match' do
  payload =
    begin
      JSON.parse(request.body.read)
    rescue JSON::ParserError
      status 400
      return({ error: 'Invalid JSON' }.to_json)
    end

  queries = payload['queries']
  unless queries.is_a?(Array)
    status 400
    return({ error: "Body must include 'queries' array" }.to_json)
  end

  if queries.length > MAX_NAMES
    status 400
    return({ error: "Too many queries (max #{MAX_NAMES})" }.to_json)
  end

  results = queries.map do |item|
    input = item['input'].to_s.strip
    cands = item['candidates']
    entry = { input: input, matched_ids: [], errors: [], mode: nil }

    unless cands.is_a?(Array)
      entry[:errors] << 'candidates must be an array'
      next entry
    end

    if cands.length > MAX_CANDIDATES_PER_NAME
      cands = cands.first(MAX_CANDIDATES_PER_NAME)
      entry[:errors] << "candidates truncated to #{MAX_CANDIDATES_PER_NAME}"
    end

    svc_entry = SERVICE.match_one(input: input, candidates: cands)
    entry.merge(svc_entry)
  end

  status 200
  { results: results }.to_json
end
