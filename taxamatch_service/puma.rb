# frozen_string_literal: true

threads_count = Integer(ENV.fetch('PUMA_THREADS', '8'))
threads threads_count, threads_count

workers Integer(ENV.fetch('PUMA_WORKERS', '1'))

port Integer(ENV.fetch('PORT', '8080'))

stdout_redirect nil, nil, true

preload_app! if ENV.fetch('RACK_ENV', 'production') == 'production'
