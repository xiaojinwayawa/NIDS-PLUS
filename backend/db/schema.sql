-- NIDS Database Schema
-- Network Intrusion Detection System

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    role VARCHAR(20) DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Models table
CREATE TABLE IF NOT EXISTS models (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL COMMENT 'lightgbm, xgboost, cnn, gru',
    version VARCHAR(20) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    dataset_type VARCHAR(50) COMMENT 'nsl-kdd, cic-ids2017',
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trained_at TIMESTAMP NULL,
    INDEX idx_type (type),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    timestamp TIMESTAMP NOT NULL,
    src_ip VARCHAR(45) NOT NULL,
    dst_ip VARCHAR(45) NOT NULL,
    src_port INT,
    dst_port INT,
    protocol VARCHAR(10),
    attack_type VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    model_id INT,
    is_false_positive BOOLEAN DEFAULT FALSE,
    marked_by INT NULL,
    marked_at TIMESTAMP NULL,
    raw_features JSON,
    INDEX idx_timestamp (timestamp),
    INDEX idx_attack_type (attack_type),
    INDEX idx_src_ip (src_ip),
    FOREIGN KEY (model_id) REFERENCES models(id),
    FOREIGN KEY (marked_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Model metrics table
CREATE TABLE IF NOT EXISTS model_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    model_id INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accuracy FLOAT,
    precision_score FLOAT,
    recall FLOAT,
    f1_score FLOAT,
    false_positive_rate FLOAT,
    false_negative_rate FLOAT,
    inference_time_ms FLOAT,
    INDEX idx_model_timestamp (model_id, timestamp),
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Traffic logs table (partitioned)
CREATE TABLE IF NOT EXISTS traffic_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    timestamp TIMESTAMP NOT NULL,
    src_ip VARCHAR(45),
    dst_ip VARCHAR(45),
    protocol VARCHAR(10),
    packet_size INT,
    is_anomaly BOOLEAN,
    prediction_confidence FLOAT,
    INDEX idx_timestamp (timestamp),
    INDEX idx_anomaly (is_anomaly)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Datasets table
CREATE TABLE IF NOT EXISTS datasets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL COMMENT 'nsl-kdd, cic-ids2017, custom',
    file_path VARCHAR(255) NOT NULL,
    file_size_mb FLOAT,
    sample_count INT,
    feature_count INT,
    class_distribution JSON,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by INT,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- System logs table
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(10) NOT NULL COMMENT 'DEBUG, INFO, WARNING, ERROR',
    module VARCHAR(50),
    message TEXT NOT NULL,
    details JSON,
    INDEX idx_timestamp (timestamp),
    INDEX idx_level (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- System config table
CREATE TABLE IF NOT EXISTS system_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    value_type VARCHAR(20) COMMENT 'string, int, float, bool, json',
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by INT,
    FOREIGN KEY (updated_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert default admin user (password: admin123)
INSERT INTO users (username, password_hash, email, role) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVr/1jrPK', 'admin@nids.local', 'admin');

-- Insert default system configuration
INSERT INTO system_config (config_key, config_value, value_type, description) VALUES
('traffic_source_mode', 'pcap', 'string', '流量源模式: pcap或live'),
('pcap_file_path', '/app/data/pcaps/sample.pcap', 'string', 'pcap文件路径'),
('network_interface', 'eth0', 'string', '网卡名称'),
('batch_size', '100', 'int', '批量推理大小'),
('inference_interval_ms', '50', 'int', '推理间隔（毫秒）'),
('alert_threshold', '0.8', 'float', '告警阈值'),
('max_queue_size', '10000', 'int', 'Redis队列最大长度'),
('enable_shap', 'true', 'bool', '是否启用SHAP分析'),
('log_level', 'INFO', 'string', '日志级别');
