use std::fs::File;
use std::io::{BufReader, Read};

pub struct BlockIterator<R: Read> {
    reader: R,
    block_size: u32,
}

impl<R: Read> BlockIterator<R> {
    pub fn new(reader: R, block_size: u32) -> Self {
        Self { reader, block_size }
    }
}

impl<R: Read> Iterator for BlockIterator<R> {
    type Item = Result<Vec<u8>, std::io::Error>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut buffer = vec![0; self.block_size as usize];
        match self.reader.read(&mut buffer) {
            Ok(0) => None,
            Ok(n) => Some(Ok(buffer[..n].to_vec())),
            Err(e) => Some(Err(e)),
        }
    }
}

pub struct DataFile {
    large: bool,
}

impl DataFile {
    const REGULAR_FILE_NAME: &str = "data.txt";
    const LARGE_FILE_NAME: &str = "large.txt";
    const DATA_DIR_PATH: &str = "data";

    pub fn new(large: bool) -> Self {
        Self { large }
    }

    pub fn chunk_iter(
        &self,
        block_size: u32,
    ) -> Result<BlockIterator<BufReader<File>>, std::io::Error> {
        let file = File::open(if self.large {
            format!("{}/{}", Self::DATA_DIR_PATH, Self::LARGE_FILE_NAME)
        } else {
            format!("{}/{}", Self::DATA_DIR_PATH, Self::REGULAR_FILE_NAME)
        })?;
        Ok(BlockIterator::new(BufReader::new(file), block_size))
    }
}
