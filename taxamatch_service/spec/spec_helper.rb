# frozen_string_literal: true

ENV['RACK_ENV'] ||= 'test'

require 'json'
require 'logger'
require 'rspec'
require 'rack/test'

require_relative '../app'
require_relative '../lib/taxamatch_service'

RSpec.configure do |config|
  config.expect_with :rspec do |c|
    c.syntax = :expect
  end
end
