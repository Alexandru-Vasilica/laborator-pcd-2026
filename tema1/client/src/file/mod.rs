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
    file_path: String,
}

impl DataFile {
    pub fn new(file_path: String) -> Self {
        Self { file_path }
    }

    pub fn chunk_iter(
        &self,
        block_size: u32,
    ) -> Result<BlockIterator<BufReader<File>>, std::io::Error> {
        let file = File::open(&self.file_path)?;
        Ok(BlockIterator::new(BufReader::new(file), block_size))
    }
}
