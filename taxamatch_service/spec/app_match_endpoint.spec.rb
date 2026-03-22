# frozen_string_literal: true

require 'spec_helper'

RSpec.describe 'POST /match' do
  include Rack::Test::Methods

  def app
    Sinatra::Application
  end

  it 'returns 400 for invalid JSON' do
    post '/match', 'not-json', { 'CONTENT_TYPE' => 'application/json' }
    expect(last_response.status).to eq(400)
    body = JSON.parse(last_response.body)
    expect(body['error']).to eq('Invalid JSON')
  end

  it 'returns 400 if queries is not an array' do
    post '/match', { queries: 'nope' }.to_json, { 'CONTENT_TYPE' => 'application/json' }
    expect(last_response.status).to eq(400)
    body = JSON.parse(last_response.body)
    expect(body['error']).to include('queries')
  end

  it 'matches single-token query against single-token candidate (genus case)' do
    payload = {
      queries: [
        {
          input: 'homo',
          candidates: [
            { id: 10, name: 'Homo' },
            { id: 11, name: 'Pan' }
          ]
        }
      ]
    }

    post '/match', payload.to_json, { 'CONTENT_TYPE' => 'application/json' }

    expect(last_response.status).to eq(200)
    body = JSON.parse(last_response.body)
    res0 = body['results'][0]

    expect(res0['mode']).to eq('single_token')
    expect(res0['matched_ids']).to include(10)
    expect(res0['matched_ids']).not_to include(11)
    expect(res0['errors']).to eq([])
  end

  it 'matches single-token query against single-token candidate (species case)' do
    payload = {
      queries: [
        {
          input: 'Sapiens',
          candidates: [
            { id: 20, name: 'sapiens' },
            { id: 21, name: 'erectus' }
          ]
        }
      ]
    }

    post '/match', payload.to_json, { 'CONTENT_TYPE' => 'application/json' }

    expect(last_response.status).to eq(200)
    body = JSON.parse(last_response.body)
    res0 = body['results'][0]

    expect(res0['mode']).to eq('single_token')
    expect(res0['matched_ids']).to include(20)
    expect(res0['matched_ids']).not_to include(21)
  end
end
