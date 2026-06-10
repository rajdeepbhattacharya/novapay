pipeline {
    agent any

    environment {
        // Datadog CI Visibility configuration
        DD_API_KEY                       = credentials('datadog-api-key')
        DD_SITE                          = 'datadoghq.com'
        DD_SERVICE                       = 'novapay-platform'
        DD_ENV                           = 'ci'
        DD_CIVISIBILITY_ENABLED          = 'true'
        DD_CIVISIBILITY_ITR_ENABLED      = 'true'
        DD_CIVISIBILITY_FLAKY_RETRY_ENABLED = 'true'

        // Build info
        DOCKER_REGISTRY = 'localhost:5000'
        BUILD_VERSION   = "${env.BUILD_NUMBER}"

        // Quality thresholds
        MIN_COVERAGE = '80'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'echo "Building NovaPay Platform v${BUILD_VERSION}"'
            }
        }

        stage('Install Dependencies') {
            parallel {
                stage('Payments') {
                    steps {
                        dir('services/payments') {
                            sh 'pip install -r requirements.txt'
                        }
                    }
                }
                stage('Lending') {
                    steps {
                        dir('services/lending') {
                            sh 'pip install -r requirements.txt'
                        }
                    }
                }
                stage('Fraud') {
                    steps {
                        dir('services/fraud') {
                            sh 'pip install -r requirements.txt'
                        }
                    }
                }
            }
        }

        stage('Run Tests') {
            parallel {
                stage('Payments Tests') {
                    environment {
                        DD_SERVICE               = 'novapay-payments'
                        DD_CIVISIBILITY_ENABLED  = 'true'
                    }
                    steps {
                        dir('services/payments') {
                            sh '''
                                pytest tests/ \
                                  --ddtrace \
                                  --cov=app \
                                  --cov-report=xml:coverage.xml \
                                  --cov-report=term-missing \
                                  --cov-fail-under=${MIN_COVERAGE} \
                                  -v \
                                  --junitxml=test-results.xml \
                                  2>&1 | tee pytest-output.txt
                            '''
                        }
                    }
                    post {
                        always {
                            dir('services/payments') {
                                junit 'test-results.xml'
                                publishCoverage adapters: [coberturaAdapter('coverage.xml')]
                            }
                        }
                    }
                }
                stage('Fraud Tests') {
                    environment {
                        DD_SERVICE               = 'novapay-fraud'
                        DD_CIVISIBILITY_ENABLED  = 'true'
                    }
                    steps {
                        dir('services/fraud') {
                            sh '''
                                pytest tests/ \
                                  --ddtrace \
                                  --cov=app \
                                  --cov-report=xml:coverage.xml \
                                  --cov-report=term-missing \
                                  --cov-fail-under=${MIN_COVERAGE} \
                                  -v \
                                  --junitxml=test-results.xml
                            '''
                        }
                    }
                    post {
                        always {
                            dir('services/fraud') {
                                junit 'test-results.xml'
                            }
                        }
                    }
                }
                stage('Lending Tests') {
                    environment {
                        DD_SERVICE               = 'novapay-lending'
                        DD_CIVISIBILITY_ENABLED  = 'true'
                    }
                    steps {
                        dir('services/lending') {
                            sh '''
                                pytest tests/ \
                                  --ddtrace \
                                  --cov=app \
                                  --cov-report=xml:coverage.xml \
                                  --cov-report=term-missing \
                                  --cov-fail-under=${MIN_COVERAGE} \
                                  -v \
                                  --junitxml=test-results.xml
                            '''
                        }
                    }
                    post {
                        always {
                            dir('services/lending') {
                                junit 'test-results.xml'
                            }
                        }
                    }
                }
            }
        }

        stage('Quality Gate Check') {
            steps {
                sh '''
                    echo "Checking quality gates..."

                    for service in payments fraud lending; do
                        coverage_file="services/$service/coverage.xml"
                        if [ -f "$coverage_file" ]; then
                            coverage=$(python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('$coverage_file')
root = tree.getroot()
rate = float(root.attrib.get('line-rate', 0)) * 100
print(f'{rate:.1f}')
")
                            echo "$service coverage: $coverage%"
                            python3 -c "
import sys
coverage = $coverage
threshold = ${MIN_COVERAGE}
if coverage < threshold:
    print(f'QUALITY GATE FAILED: $service coverage {coverage:.1f}% is below {threshold}%')
    sys.exit(1)
else:
    print(f'QUALITY GATE PASSED: $service coverage {coverage:.1f}% >= {threshold}%')
"
                        fi
                    done
                '''
            }
        }

        stage('Build Docker Images') {
            when {
                expression { currentBuild.result == null || currentBuild.result == 'SUCCESS' }
            }
            parallel {
                stage('Build Payments') {
                    steps {
                        dir('services/payments') {
                            sh 'docker build -t novapay-payments:${BUILD_VERSION} -t novapay-payments:latest .'
                        }
                    }
                }
                stage('Build Fraud') {
                    steps {
                        dir('services/fraud') {
                            sh 'docker build -t novapay-fraud:${BUILD_VERSION} -t novapay-fraud:latest .'
                        }
                    }
                }
                stage('Build Lending') {
                    steps {
                        dir('services/lending') {
                            sh 'docker build -t novapay-lending:${BUILD_VERSION} -t novapay-lending:latest .'
                        }
                    }
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    # Load images into minikube
                    minikube image load novapay-payments:latest
                    minikube image load novapay-fraud:latest
                    minikube image load novapay-lending:latest

                    # Apply K8s manifests
                    kubectl apply -f k8s/namespace.yaml
                    kubectl apply -f k8s/payments/
                    kubectl apply -f k8s/fraud/
                    kubectl apply -f k8s/lending/

                    # Wait for rollout
                    kubectl rollout status deployment/novapay-payments -n novapay --timeout=120s
                    kubectl rollout status deployment/novapay-fraud    -n novapay --timeout=120s
                    kubectl rollout status deployment/novapay-lending  -n novapay --timeout=120s

                    echo "Deployment complete!"
                '''
            }
        }
    }

    post {
        always {
            sh '''
                echo "Pipeline complete. Build: ${BUILD_NUMBER}, Status: ${currentBuild.currentResult}"
            '''
        }
        success {
            sh 'echo "NovaPay Platform deployed successfully"'
        }
        failure {
            sh 'echo "Pipeline failed - check quality gates and test results"'
        }
    }
}
