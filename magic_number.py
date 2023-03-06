#! /usr/bin/env python3
# -*- encoding:utf-8 -*-


from typing import BinaryIO, MutableMapping, Sequence

from d2l.trie import Trie

magic_numbers: dict[str, dict[str, list[tuple[int, bytes]]|str]] = {
    '123': {
        'signs': [(0, b'\x00\x00\x1a\x00\x05\x10\x04')],
        'mime': 'application/vnd.lotus-1-2-3'
    },
    'cpl': {
        'signs': [(0, b'MZ'), (0, b'\xdc\xdc')],
        'mime': 'application/cpl+xml'
    },
    'epub': {
        'signs': [(0, b'PK\x03\x04\n\x00\x02\x00')],
        'mime': 'application/epub+zip'
    },
    'ttf': {
        'signs': [(0, b'\x00\x01\x00\x00\x00')],
        'mime': 'application/font-sfnt'
    },
    'gz': {
        'signs': [(0, b'\x1f\x8b\x08')],
        'mime': 'application/gzip'
    },
    'tgz': {
        'signs': [(0, b'\x1f\x8b\x08')],
        'mime': 'application/gzip'
    },
    'hqx': {
        'signs': [(0, b'(This file must be converted with BinHex ')],
        'mime': 'application/mac-binhex40',
    },
    'doc': {
        'signs': [
            (0, b'\rDOC'),
            (0, b'\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00'),
            (0, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
            (0, b'\xdb\xa5-\x00'),
            (512, b'\xec\xa5\xc1\x00'),
        ],
        'mime': 'application/msword',
    },
    'mxf': {
        'signs': [
            (0, b'\x06\x0e+4\x02\x05\x01\x01\r\x01\x02\x01\x01\x02'),
            (0, b'<CTransTimeline>'),
        ],
        'mime': 'application/mxf',
    },
    'lha': {
        'signs': [(2, b'-lh')],
        'mime': 'application/octet-stream'
    },
    'lzh': {
        'signs': [(2, b'-lh')],
        'mime': 'application/octet-stream'
    },
    'exe': {
        'signs': [(0, b'MZ')],
        'mime': 'application/octet-stream'
    },
    'class': {
        'signs': [(0, b'\xca\xfe\xba\xbe')],
        'mime': 'application/octet-stream'
    },
    'dll': {
        'signs': [(0, b'MZ')],
        'mime': 'application/octet-stream'
    },
    'img': {
        'signs': [
            (0, b'\x00\x01\x00\x00Standard Jet DB'),
            (0, b'PICT\x00\x08'),
            (0, b'QFI\xfb'),
            (0, b'SCMI'),
            (0, b'~t,\x01Pp\x02MR\x01\x00\x00\x00\x08\x00\x00\x00\x01\x00\x001\x00\x00\x001\x00\x00\x00C\x01\xff\x00\x01\x00\x08\x00\x01\x00\x00\x00~t,\x01'),
            (0, b'\xeb<\x90*'),
        ],
        'mime': 'application/octet-stream',
    },
    'iso': {
        'signs': [(32769, b'CD001'), (34817, b'CD001'), (36865, b'CD001')],
        'mime': 'application/octet-stream',
    },
    'ogx': {
        'signs': [(0, b'OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00')],
        'mime': 'application/ogg',
    },
    'oxps': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/oxps'
    },
    'pdf': {
        'signs': [(0, b'%PDF')],
        'mime': 'application/pdf'
    },
    'p10': {
        'signs': [(0, b'd\x00\x00\x00')],
        'mime': 'application/pkcs10'
    },
    'pls': {
        'signs': [(0, b'[playlist]')],
        'mime': 'application/pls+xml'
    },
    'eps': {
        'signs': [(0, b'%!PS-Adobe-3.0 EPSF-3 0'), (0, b'\xc5\xd0\xd3\xc6')],
        'mime': 'application/postscript',
    },
    'ai': {
        'signs': [(0, b'%PDF')],
        'mime': 'application/postscript'
    },
    'rtf': {
        'signs': [(0, b'{\\rtf1')],
        'mime': 'application/rtf'
    },
    'tsa': {
        'signs': [(0, b'G')],
        'mime': 'application/tamp-sequence-adjust'
    },
    'msf': {
        'signs': [(0, b'// <!-- <mdb:mork:z')],
        'mime': 'application/vnd.epson.msf'
    },
    'fdf': {
        'signs': [(0, b'%PDF')],
        'mime': 'application/vnd.fdf'
    },
    'fm': {
        'signs': [(0, b'<MakerFile ')],
        'mime': 'application/vnd.framemaker'
    },
    'kmz': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/vnd.google-earth.kmz'
    },
    'tpl': {
        'signs': [(0, b'\x00 \xaf0'), (0, b'msFilterList')],
        'mime': 'application/vnd.groove-tool-template',
    },
    'kwd': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/vnd.kde.kword'
    },
    'wk4': {
        'signs': [(0, b'\x00\x00\x1a\x00\x02\x10\x04\x00\x00\x00\x00\x00')],
        'mime': 'application/vnd.lotus-1-2-3',
    },
    'wk3': {
        'signs': [(0, b'\x00\x00\x1a\x00\x00\x10\x04\x00\x00\x00\x00\x00')],
        'mime': 'application/vnd.lotus-1-2-3',
    },
    'wk1': {
        'signs': [(0, b'\x00\x00\x02\x00\x06\x04\x06\x00\x08\x00\x00\x00\x00\x00')],
        'mime': 'application/vnd.lotus-1-2-3',
    },
    'apr': {
        'signs': [(0, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')],
        'mime': 'application/vnd.lotus-approach',
    },
    'nsf': {
        'signs': [(0, b'\x1a\x00\x00\x04\x00\x00'), (0, b'NESM\x1a\x01')],
        'mime': 'application/vnd.lotus-notes',
    },
    'ntf': {
        'signs': [(0, b'\x1a\x00\x00'), (0, b'01ORDNANCE SURVEY       '), (0, b'NITF0')],
        'mime': 'application/vnd.lotus-notes',
    },
    'org': {
        'signs': [(0, b'AOLVM100')],
        'mime': 'application/vnd.lotus-organizer'
    },
    'lwp': {
        'signs': [(0, b'WordPro')],
        'mime': 'application/vnd.lotus-wordpro'
    },
    'sam': {
        'signs': [(0, b'[Phone]')],
        'mime': 'application/vnd.lotus-wordpro'
    },
    'mif': {
        'signs': [(0, b'<MakerFile '), (0, b'Version ')],
        'mime': 'application/vnd.mif'
    },
    'xul': {
        'signs': [(0, b'<?xml version="1.0"?>')],
        'mime': 'application/vnd.mozilla.xul+xml'
    },
    'asf': {
        'signs': [(0, b'0&\xb2u\x8ef\xcf\x11\xa6\xd9\x00\xaa\x00b\xcel')],
        'mime': 'application/vnd.ms-asf',
    },
    'cab': {
        'signs': [(0, b'ISc('), (0, b'MSCF')],
        'mime': 'application/vnd.ms-cab-compressed'
    },
    'xls': {
        'signs': [
            (512, b'\t\x08\x10\x00\x00\x06\x05\x00'),
            (0, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
            (512, b'\xfd\xff\xff\xff\x04'),
            (512, b'\xfd\xff\xff\xff \x00\x00\x00'),
        ],
        'mime': 'application/vnd.ms-excel',
    },
    'xla': {
        'signs': [(0, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')],
        'mime': 'application/vnd.ms-excel',
    },
    'chm': {
        'signs': [(0, b'ITSF')],
        'mime': 'application/vnd.ms-htmlhelp'
    },
    'ppt': {
        'signs': [
            (512, b'\x00n\x1e\xf0'),
            (512, b'\x0f\x00\xe8\x03'),
            (512, b'\xa0F\x1d\xf0'),
            (0, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
            (512, b'\xfd\xff\xff\xff\x04'),
        ],
        'mime': 'application/vnd.ms-powerpoint',
    },
    'pps': {
        'signs': [(0, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')],
        'mime': 'application/vnd.ms-powerpoint',
    },
    'wks': {
        'signs': [(0, b'\x0eWKS'), (0, b'\xff\x00\x02\x00\x04\x04\x05T\x02\x00')],
        'mime': 'application/vnd.ms-works',
    },
    'wpl': {
        'signs': [(84, b'Microsoft Windows Media Player -- ')],
        'mime': 'application/vnd.ms-wpl',
    },
    'xps': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/vnd.ms-xpsdocument'
    },
    'cif': {
        'signs': [(2, b'[Version')],
        'mime': 'application/vnd.multiad.creator.cif'
    },
    'odp': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/vnd.oasis.opendocument.presentation',
    },
    'odt': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/vnd.oasis.opendocument.text'
    },
    'ott': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/vnd.oasis.opendocument.text-template',
    },
    'pptx': {
        'signs': [(0, b'PK\x03\x04\x14\x00\x06\x00')],
        'mime': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    },
    'xlsx': {
        'signs': [(0, b'PK\x03\x04\x14\x00\x06\x00')],
        'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    },
    'docx': {
        'signs': [(0, b'PK\x03\x04\x14\x00\x06\x00')],
        'mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    },
    'prc': {
        'signs': [(0, b'BOOKMOBI'), (60, b'tBMPKnWr')],
        'mime': 'application/vnd.palm'
    },
    'pdb': {
        'signs': [
            (11, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'),
            (0, b'M-W Pocket Dicti'),
            (0, b'Microsoft C/C++ '),
            (0, b'sm_'),
            (0, b'szez'),
            (0, b'\xac\xed\x00\x05sr\x00\x12bgblitz.'),
        ],
        'mime': 'application/vnd.palm',
    },
    'qxd': {
        'signs': [(0, b'\x00\x00MMXPR')],
        'mime': 'application/vnd.Quark.QuarkXPress'
    },
    'rar': {
        'signs': [(0, b'Rar!\x1a\x07\x00'), (0, b'Rar!\x1a\x07\x01\x00')],
        'mime': 'application/vnd.rar',
    },
    'mmf': {
        'signs': [(0, b'MMMD\x00\x00')],
        'mime': 'application/vnd.smaf'
    },
    'cap': {
        'signs': [(0, b'RTSS'), (0, b'XCP\x00')],
        'mime': 'application/vnd.tcpdump.pcap'
    },
    'dmp': {
        'signs': [(0, b'MDMP\x93\xa7'), (0, b'PAGEDU64'), (0, b'PAGEDUMP')],
        'mime': 'application/vnd.tcpdump.pcap',
    },
    'wpd': {
        'signs': [(0, b'\xffWPC')],
        'mime': 'application/vnd.wordperfect'
    },
    'xar': {
        'signs': [(0, b'xar!')],
        'mime': 'application/vnd.xara'
    },
    'spf': {
        'signs': [(0, b'SPFI\x00')],
        'mime': 'application/vnd.yamaha.smaf-phrase'
    },
    'dtd': {
        'signs': [(0, b'\x07dt2ddtd')],
        'mime': 'application/xml-dtd'
    },
    'zip': {
        'signs': [
            (0, b'PK\x03\x04'),
            (0, b'PK\x03\x04'),
            (0, b'PK\x03\x04\x14\x00\x01\x00c\x00\x00\x00\x00\x00'),
            (0, b'PK\x07\x08'),
            (30, b'PKLITE'),
            (526, b'PKSpX'),
            (29152, b'WinZip'),
        ],
        'mime': 'application/zip',
    },
    'amr': {
        'signs': [(0, b'#!AMR')],
        'mime': 'audio/AMR'
    },
    'au': {
        'signs': [(0, b'.snd'), (0, b'dns.')],
        'mime': 'audio/basic'
    },
    'm4a': {
        'signs': [(0, b'\x00\x00\x00 ftypM4A '), (4, b'ftypM4A ')],
        'mime': 'audio/mp4'
    },
    'mp3': {
        'signs': [(0, b'ID3'), (0, b'\xff\xfb')],
        'mime': 'audio/mpeg'
    },
    'oga': {
        'signs': [(0, b'OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00')],
        'mime': 'audio/ogg'
    },
    'ogg': {
        'signs': [(0, b'OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00')],
        'mime': 'audio/ogg'
    },
    'qcp': {
        'signs': [(0, b'RIFF')],
        'mime': 'audio/qcelp'
    },
    'koz': {
        'signs': [(0, b'ID3\x03\x00\x00\x00')],
        'mime': 'audio/vnd.audikoz'
    },
    'bmp': {
        'signs': [(0, b'BM')],
        'mime': 'image/bmp'
    },
    'dib': {
        'signs': [(0, b'BM')],
        'mime': 'image/bmp'
    },
    'emf': {
        'signs': [(0, b'\x01\x00\x00\x00')],
        'mime': 'image/emf'
    },
    'fits': {
        'signs': [(0, b'SIMPLE  =                    T')],
        'mime': 'image/fits'
    },
    'gif': {
        'signs': [(0, b'GIF89a')],
        'mime': 'image/gif'
    },
    'jp2': {
        'signs': [(0, b'\x00\x00\x00\x0cjP  \r\n')],
        'mime': 'image/jp2'
    },
    'jpg': {
        'signs': [(0, b'\xff\xd8'), (0, b'\xff\xd8'), (0, b'\xff\xd8'), (0, b'\xff\xd8')],
        'mime': 'image/jpeg',
    },
    'jpeg': {
        'signs': [(0, b'\xff\xd8'), (0, b'\xff\xd8')],
        'mime': 'image/jpeg'
    },
    'jpe': {
        'signs': [(0, b'\xff\xd8'), (0, b'\xff\xd8')],
        'mime': 'image/jpeg'
    },
    'jfif': {
        'signs': [(0, b'\xff\xd8')],
        'mime': 'image/jpeg'
    },
    'png': {
        'signs': [(0, b'\x89PNG\r\n\x1a\n')],
        'mime': 'image/png'
    },
    'tiff': {
        'signs': [(0, b'I I'), (0, b'II*\x00'), (0, b'MM\x00*'), (0, b'MM\x00+')],
        'mime': 'image/tiff',
    },
    'tif': {
        'signs': [(0, b'I I'), (0, b'II*\x00'), (0, b'MM\x00*'), (0, b'MM\x00+')],
        'mime': 'image/tiff',
    },
    'psd': {
        'signs': [(0, b'8BPS')],
        'mime': 'image/vnd.adobe.photoshop'
    },
    'dwg': {
        'signs': [(0, b'AC10')],
        'mime': 'image/vnd.dwg'
    },
    'ico': {
        'signs': [(0, b'\x00\x00\x01\x00')],
        'mime': 'image/vnd.microsoft.icon'
    },
    'mdi': {
        'signs': [(0, b'EP')],
        'mime': 'image/vnd.ms-modi'
    },
    'hdr': {
        'signs': [(0, b'#?RADIANCE\n'), (0, b'ISc(')],
        'mime': 'image/vnd.radiance'
    },
    'pcx': {
        'signs': [(512, b'\t\x08\x10\x00\x00\x06\x05\x00')],
        'mime': 'image/vnd.zbrush.pcx'
    },
    'wmf': {
        'signs': [(0, b'\x01\x00\t\x00\x00\x03'), (0, b'\xd7\xcd\xc6\x9a')],
        'mime': 'image/wmf',
    },
    'eml': {
        'signs': [(0, b'From: '), (0, b'Return-Path: '), (0, b'X-')],
        'mime': 'message/rfc822'
    },
    'art': {
        'signs': [(0, b'JG\x04\x0e')],
        'mime': 'message/rfc822'
    },
    'manifest': {
        'signs': [(0, b'<?xml version=')],
        'mime': 'text/cache-manifest'
    },
    'log': {
        'signs': [(0, b'***  Installation Started ')],
        'mime': 'text/plain'
    },
    'tsv': {
        'signs': [(0, b'G')],
        'mime': 'text/tab-separated-values'
    },
    'vcf': {
        'signs': [(0, b'BEGIN:VCARD\r\n')],
        'mime': 'text/vcard'
    },
    'dms': {
        'signs': [(0, b'DMS!')],
        'mime': 'text/vnd.DMClientScript'
    },
    'dot': {
        'signs': [(0, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')],
        'mime': 'text/vnd.graphviz'
    },
    'ts': {
        'signs': [(0, b'G')],
        'mime': 'text/vnd.trolltech.linguist'
    },
    '3gp': {
        'signs': [(0, b'\x00\x00\x00\x14ftyp3gp'), (0, b'\x00\x00\x00 ftyp3gp')],
        'mime': 'video/3gpp',
    },
    '3g2': {
        'signs': [(0, b'\x00\x00\x00\x14ftyp3gp'), (0, b'\x00\x00\x00 ftyp3gp')],
        'mime': 'video/3gpp2',
    },
    'mp4': {
        'signs': [
            (0, b'\x00\x00\x00\x14ftypisom'),
            (0, b'\x00\x00\x00\x18ftyp3gp5'),
            (0, b'\x00\x00\x00\x1cftypMSNV\x01)\x00FMSNVmp42'),
            (4, b'ftyp3gp5'),
            (4, b'ftypMSNV'),
            (4, b'ftypisom'),
        ],
        'mime': 'video/mp4',
    },
    'm4v': {
        'signs': [
            (0, b'\x00\x00\x00\x18ftypmp42'),
            (0, b'\x00\x00\x00 ftypM4V '),
            (4, b'ftypmp42'),
        ],
        'mime': 'video/mp4',
    },
    'mpeg': {
        'signs': [(0, b'\x00\x00\x01\x00'), (0, b'\xff\xd8')],
        'mime': 'video/mpeg'
    },
    'mpg': {
        'signs': [(0, b'\x00\x00\x01\x00'), (0, b'\x00\x00\x01\xba'), (0, b'\xff\xd8')],
        'mime': 'video/mpeg',
    },
    'ogv': {
        'signs': [(0, b'OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00')],
        'mime': 'video/ogg'
    },
    'mov': {
        'signs': [(0, b'\x00'), (0, b'\x00\x00\x00\x14ftypqt  '), (4, b'ftypqt  '), (4, b'moov')],
        'mime': 'video/quicktime',
    },
    'cpt': {
        'signs': [(0, b'CPT7FILE'), (0, b'CPTFILE')],
        'mime': 'application/mac-compactpro'
    },
    'sxc': {
        'signs': [(0, b'PK\x03\x04'), (0, b'PK\x03\x04')],
        'mime': 'application/vnd.sun.xml.calc',
    },
    'sxd': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/vnd.sun.xml.draw'
    },
    'sxi': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/vnd.sun.xml.impress'
    },
    'sxw': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/vnd.sun.xml.writer'
    },
    'bz2': {
        'signs': [(0, b'BZh')],
        'mime': 'application/x-bzip2'
    },
    'vcd': {
        'signs': [(0, b'ENTRYVCD\x02\x00\x00\x01\x02\x00\x18X')],
        'mime': 'application/x-cdlink',
    },
    'csh': {
        'signs': [(0, b'cush\x00\x00\x00\x02\x00\x00\x00')],
        'mime': 'application/x-csh'
    },
    'spl': {
        'signs': [(0, b'\x00\x00\x01\x00')],
        'mime': 'application/x-futuresplash'
    },
    'jar': {
        'signs': [
            (0, b'JARCS\x00'),
            (0, b'PK\x03\x04'),
            (0, b'PK\x03\x04\x14\x00\x08\x00\x08\x00'),
            (0, b"_'\xa8\x89"),
        ],
        'mime': 'application/x-java-archive',
    },
    'rpm': {
        'signs': [(0, b'\xed\xab\xee\xdb')],
        'mime': 'application/x-rpm'
    },
    'swf': {
        'signs': [(0, b'CWS'), (0, b'FWS'), (0, b'ZWS')],
        'mime': 'application/x-shockwave-flash',
    },
    'sit': {
        'signs': [(0, b'SIT!\x00'), (0, b'StuffIt (c)1997-')],
        'mime': 'application/x-stuffit'
    },
    'tar': {
        'signs': [(257, b'ustar')],
        'mime': 'application/x-tar'
    },
    'xpi': {
        'signs': [(0, b'PK\x03\x04')],
        'mime': 'application/x-xpinstall'
    },
    'xz': {
        'signs': [(0, b'\xfd7zXZ\x00')],
        'mime': 'application/x-xz'
    },
    'mid': {
        'signs': [(0, b'MThd')],
        'mime': 'audio/midi'
    },
    'midi': {
        'signs': [(0, b'MThd')],
        'mime': 'audio/midi'
    },
    'aiff': {
        'signs': [(0, b'FORM\x00')],
        'mime': 'audio/x-aiff'
    },
    'flac': {
        'signs': [(0, b'fLaC\x00\x00\x00"')],
        'mime': 'audio/x-flac'
    },
    'wma': {
        'signs': [(0, b'0&\xb2u\x8ef\xcf\x11\xa6\xd9\x00\xaa\x00b\xcel')],
        'mime': 'audio/x-ms-wma',
    },
    'ram': {
        'signs': [(0, b'rtsp://')],
        'mime': 'audio/x-pn-realaudio'
    },
    'rm': {
        'signs': [(0, b'.RMF')],
        'mime': 'audio/x-pn-realaudio'
    },
    'ra': {
        'signs': [(0, b'.RMF\x00\x00\x00\x12\x00'), (0, b'.ra\xfd\x00')],
        'mime': 'audio/x-realaudio',
    },
    'wav': {
        'signs': [(0, b'RIFF')],
        'mime': 'audio/x-wav'
    },
    'webp': {
        'signs': [(0, b'RIFF')],
        'mime': 'image/webp'
    },
    'pgm': {
        'signs': [(0, b'P5\n')],
        'mime': 'image/x-portable-graymap'
    },
    'rgb': {
        'signs': [(0, b'\x01\xda\x01\x01\x00\x03')],
        'mime': 'image/x-rgb'
    },
    'webm': {
        'signs': [(0, b'\x1aE\xdf\xa3')],
        'mime': 'video/webm'
    },
    'flv': {
        'signs': [(0, b'\x00\x00\x00 ftypM4V '), (0, b'FLV\x01')],
        'mime': 'video/x-flv'
    },
    'mkv': {
        'signs': [(0, b'\x1aE\xdf\xa3')],
        'mime': 'video/x-matroska'
    },
    'asx': {
        'signs': [(0, b'<')],
        'mime': 'video/x-ms-asf'
    },
    'wmv': {
        'signs': [(0, b'0&\xb2u\x8ef\xcf\x11\xa6\xd9\x00\xaa\x00b\xcel')],
        'mime': 'video/x-ms-wmv',
    },
    'avi': {
        'signs': [(0, b'RIFF')],
        'mime': 'video/x-msvideo'
    },
}

__magic_trie: Sequence[MutableMapping[bytes, tuple[str, str]]] = []
__video_trie: Sequence[MutableMapping[bytes, bool]] = []
__max_bytes: int = 0
__max_bytes_video: int = 0
def __init__():
    global __max_bytes, __max_bytes_video
    for ext, item in magic_numbers.items():
        mime: str = item['mime'] # type: ignore
        signs: list[tuple[int, bytes]] = item['signs'] # type: ignore
        for head, sign in signs:
            while len(__magic_trie) <= head + 1:
                __magic_trie.append(Trie())
            __magic_trie[head][sign] = (ext, mime)
            if __max_bytes < head + len(sign):
                __max_bytes = head + len(sign)
        if mime.startswith('video/'):
            for head, sign in signs:
                while len(__video_trie) <= head + 1:
                    __video_trie.append(Trie())
                __video_trie[head][sign] = True
                if __max_bytes_video < head + len(sign):
                    __max_bytes_video = head + len(sign)
__init__()
def classify(file: BinaryIO) -> tuple[str, str] | None:
    header = file.read(__max_bytes)
    for t in __magic_trie:
        v = t.get(header, None)
        if v is None:
            header = header[1:]
        else:
            return v
def video(file: BinaryIO) -> bool:
    header = file.read(__max_bytes)
    for t in __video_trie:
        v = t.get(header, None)
        if v is None:
            header = header[1:]
        else:
            return v
    return False
