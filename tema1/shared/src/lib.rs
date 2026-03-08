use std::{collections::HashMap, str::FromStr, sync::LazyLock};
use thiserror::Error;

pub mod quic;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Transport {
    Tcp,
    Udp,
    UdpStopAndWait,
    Quic,
    QuicStopAndWait,
}

#[derive(Debug, Error)]
pub enum ParseTransportError {
    #[error("Invalid transport")]
    InvalidTransport,
}

pub const MAX_BLOCK_SIZE: usize = 65535;

impl FromStr for Transport {
    type Err = ParseTransportError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "tcp" => Ok(Transport::Tcp),
            "udp" => Ok(Transport::Udp),
            "udp-stop-and-wait" => Ok(Transport::UdpStopAndWait),
            "quic" => Ok(Transport::Quic),
            "quic-stop-and-wait" => Ok(Transport::QuicStopAndWait),
            _ => Err(ParseTransportError::InvalidTransport),
        }
    }
}

pub static ADDRESSES: LazyLock<HashMap<Transport, String>> = LazyLock::new(|| {
    HashMap::from([
        (Transport::Tcp, "127.0.0.1:8080".to_string()),
        (Transport::Udp, "127.0.0.1:8081".to_string()),
        (Transport::UdpStopAndWait, "127.0.0.1:8082".to_string()),
        (Transport::Quic, "127.0.0.1:8083".to_string()),
        (Transport::QuicStopAndWait, "127.0.0.1:8084".to_string()),
    ])
});

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct LenHeader {
    pub len: usize,
}

impl LenHeader {
    pub fn to_bytes(&self) -> [u8; 4] {
        (self.len as u32).to_le_bytes()
    }

    pub fn from_bytes(bytes: [u8; 4]) -> Self {
        Self {
            len: u32::from_le_bytes(bytes) as usize,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct UdpPayload {
    pub seq: u64,
    pub data: Vec<u8>,
}

impl UdpPayload {
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(8 + self.data.len());
        bytes.extend_from_slice(&(self.seq as u64).to_le_bytes());
        bytes.extend_from_slice(&self.data);
        bytes
    }

    pub fn from_bytes(bytes: &[u8]) -> Self {
        let seq = u64::from_le_bytes(bytes[..8].try_into().unwrap());
        let data = bytes[8..].to_vec();
        Self { seq, data }
    }
}

pub struct UdpAck {
    pub seq: u64,
}

impl UdpAck {
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(8);
        bytes.extend_from_slice(&(self.seq as u64).to_le_bytes());
        bytes
    }

    pub fn from_bytes(bytes: &[u8]) -> Self {
        Self {
            seq: u64::from_le_bytes(bytes[..8].try_into().unwrap()),
        }
    }
}
