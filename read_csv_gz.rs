// get CUSIP, Symbol mapping from gzipped csv
// check if CUSIP is in xref
// if in xref, add price data to sdds
// if not in xref, report missing

use std::fs::File;
use std::io::BufReader;
use flate2::read::GzDecoder;
use std::io::Read;
use encoding_rs::WINDOWS_1252;

use std::env;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        eprintln!("Usage: {} <file_path>", args[0]);
        std::process::exit(1);
    }

    let file_path = &args[1];
    let taq_file = File::open(file_path).unwrap();
    let mut gz_decoder = GzDecoder::new(taq_file);
    let mut encoded_content = Vec::new();
    gz_decoder.read_to_end(&mut encoded_content).unwrap();

    let (decoded_content, _, _) = WINDOWS_1252.decode(&encoded_content);
    let buf_reader = BufReader::new(decoded_content.as_bytes());
    let mut taq_reader = csv::ReaderBuilder::new()
        .delimiter(b'|')
        .flexible(true)
        .has_headers(false)
        .from_reader(buf_reader);

    for result in taq_reader.records() {
        match result {
            Ok(record) => {
                // "Symbol", "Security_Description", "CUSIP", "Security_Type", "SIP_Symbol", "Old_Symbol", "Test_Symbol_Flag", "Listed_Exchange", "Tape", "Unit_Of_Trade", "Round_Lot", "NYSE_Industry_Code", "Shares_Outstanding", "Halt_Delay_Reason", "Specialist_Clearing_Agent", "Specialist_Clearing_Number", "Specialist_Post_Number", "Specialist_Panel", "TradedOnNYSEMKT", "TradedOnNASDAQBX", "TradedOnNSX", "TradedOnFINRA", "TradedOnISE", "TradedOnEdgeA", "TradedOnEdgeX", "TradedOnCHX", "TradedOnNYSE", "TradedOnArca", "TradedOnNasdaq", "TradedOnCBOE", "TradedOnPSX", "TradedOnBATSY", "TradedOnBATS", "TradedOnIEX", "Tick_Pilot_Indicator", "Effective_Date", "TradedOnLTSE", "TradedOnMEMX", "TradedOnMIAX"
                // println!("Record: {:?}", record);
                if record.len() > 2 {
                    let cusip = &record[2];
                    let symbol = &record[0];
                    let sip_symbol = &record[4];
                    if !cusip.is_empty() && symbol != "END" {
                        println!("{}, {}, {}", cusip, symbol, sip_symbol);
                    }
                }
            }
            Err(e) => eprintln!("Error reading CSV record: {}", e),
        }
    }
}
