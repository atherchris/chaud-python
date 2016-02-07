#!/usr/bin/env python3

#
# Copyright (c) 2016, Christopher Atherton <the8lack8ox@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

import os
import re
import sys
import time

import argparse
import tempfile
import base64
import datetime
import imghdr
import shutil

import concurrent.futures
import multiprocessing
import subprocess

PROGRAM_NAME='chaud'
"""Change Audio"""

tmpdir = tempfile.TemporaryDirectory( prefix=PROGRAM_NAME+'-' )

def free_filename( ext='.tmp' ):
	with tempfile.NamedTemporaryFile( suffix=ext, dir=tmpdir.name ) as tf:
		return tf.name

FORMAT_EXT_MAP = {
	'aac':		'.m4a',
	'flac':		'.flac',
	'mp3':		'.mp3',
	'opus':		'.opus',
	'vorbis':	'.ogg',
	'wav':		'.wav',
	'wavpack':	'.wv'
}
"""Map of supported format names and extensions"""

# Regular expressions for AAC tag extraction
AAC_TITLE_RE		= re.compile( r'    title = (.+)' )
AAC_ARTIST_RE		= re.compile( r'    artist = (.+)' )
AAC_ALBUM_RE		= re.compile( r'    album = (.+)' )
AAC_TRACK_RE		= re.compile( r'    track = (\d+)' )
AAC_DISC_RE			= re.compile( r'    disc = (\d+)' )
AAC_GENRE_RE		= re.compile( r'    genre = (.+)' )
AAC_YEAR_RE			= re.compile( r'    year = (\d+)' )
AAC_COMMENT_RE		= re.compile( r'    comment = (.+)' )

# Regular expressions for FLAC tag extraction
FLAC_TITLE_RE		= re.compile( r'    comment\[\d+\]: TITLE=(.+)', re.I )
FLAC_ARTIST_RE		= re.compile( r'    comment\[\d+\]: ARTIST=(.+)', re.I )
FLAC_ALBUM_RE		= re.compile( r'    comment\[\d+\]: ALBUM=(.+)', re.I )
FLAC_TRACK_RE		= re.compile( r'    comment\[\d+\]: TRACKNUMBER=(\d+)', re.I )
FLAC_DISC_RE		= re.compile( r'    comment\[\d+\]: DISCNUMBER=(\d+)', re.I )
FLAC_GENRE_RE		= re.compile( r'    comment\[\d+\]: GENRE=(.+)', re.I )
FLAC_YEAR_RE		= re.compile( r'    comment\[\d+\]: DATE=(\d+)(\D\d+\D\d+)?', re.I )
FLAC_COMMENT_RE		= re.compile( r'    comment\[\d+\]: COMMENT=(.+)', re.I )

# Regular expressions for OPUS tag extraction
OPUS_TITLE_RE		= re.compile( r'\tTITLE=(.+)', re.I )
OPUS_ARTIST_RE		= re.compile( r'\tARTIST=(.+)', re.I )
OPUS_ALBUM_RE		= re.compile( r'\tALBUM=(.+)', re.I )
OPUS_TRACK_RE		= re.compile( r'\tTRACKNUMBER=(\d+)', re.I )
OPUS_DISC_RE		= re.compile( r'\tDISCNUMBER=(\d+)', re.I )
OPUS_GENRE_RE		= re.compile( r'\tGENRE=(.+)', re.I )
OPUS_YEAR_RE		= re.compile( r'\tDATE=(\d+)(\D\d+\D\d+)?', re.I )
OPUS_COMMENT_RE		= re.compile( r'\tCOMMENT=(.+)', re.I )
#OPUS_COVER_RE		= re.compile( r'\tMETADATA_BLOCK_PICTURE=(.+)', re.I )

# Regular expressions for VORBIS tag extraction
VORBIS_TITLE_RE		= re.compile( r'TITLE=(.+)', re.I )
VORBIS_ARTIST_RE	= re.compile( r'ARTIST=(.+)', re.I )
VORBIS_ALBUM_RE		= re.compile( r'ALBUM=(.+)', re.I )
VORBIS_TRACK_RE		= re.compile( r'TRACKNUMBER=(\d+)', re.I )
VORBIS_DISC_RE		= re.compile( r'DISCNUMBER=(\d+)', re.I )
VORBIS_GENRE_RE		= re.compile( r'GENRE=(.+)', re.I )
VORBIS_YEAR_RE		= re.compile( r'DATE=(\d+)(\D\d+\D\d+)?', re.I )
VORBIS_COMMENT_RE	= re.compile( r'COMMENT=(.+)', re.I )
VORBIS_COVER_RE		= re.compile( r'METADATA_BLOCK_PICTURE=(.+)', re.I )

# Regular expressions for WAVPACK tag extraction
WAVPACK_TITLE_RE	= re.compile( r'Title:\s+(.+)' )
WAVPACK_ARTIST_RE	= re.compile( r'Artist:\s+(.+)' )
WAVPACK_ALBUM_RE	= re.compile( r'Album:\s+(.+)' )
WAVPACK_TRACK_RE	= re.compile( r'Track:\s+(\d+)' )
WAVPACK_DISC_RE		= re.compile( r'Disc:\s+(\d+)' )	# ?
WAVPACK_GENRE_RE	= re.compile( r'Genre:\s+(.+)' )
WAVPACK_YEAR_RE		= re.compile( r'Year:\s+(\d+)' )
WAVPACK_COMMENT_RE	= re.compile( r'Comment:\s+(.+)' )
WAVPACK_COVER_RE	= re.compile( r'Cover Art \(Front\):\s+(.+)' )


#
# MP3 tag stuff
#

ID3V1_GENRES=(
	'Blues', 'ClassicRock', 'Country', 'Dance', 'Disco', 'Funk', 'Grunge',
	'Hip-Hop', 'Jazz', 'Metal', 'NewAge', 'Oldies', 'Other', 'Pop', 'R&B',
	'Rap', 'Reggae', 'Rock', 'Techno', 'Industrial', 'Alternative', 'Ska',
	'DeathMetal', 'Pranks', 'Soundtrack', 'Euro-Techno', 'Ambient', 'Trip-Hop',
	'Vocal', 'Jazz+Funk', 'Fusion', 'Trance', 'Classical', 'Instrumental',
	'Acid', 'House', 'Game', 'SoundClip', 'Gospel', 'Noise', 'AlternativeRock',
	'Bass', 'Soul', 'Punk', 'Space', 'Meditative', 'InstrumentalPop',
	'InstrumentalRock', 'Ethnic', 'Gothic', 'Darkwave', 'Techno-Industrial',
	'Electronic', 'Pop-Folk', 'Eurodance', 'Dream', 'SouthernRock', 'Comedy',
	'Cult', 'GangstaRap', 'Top40', 'ChristianRap', 'Pop/Funk', 'Jungle',
	'NativeAmerican', 'Cabaret', 'NewWave', 'Psychadelic', 'Rave', 'Showtunes',
	'Trailer', 'Lo-Fi', 'Tribal', 'AcidPunk', 'AcidJazz', 'Polka', 'Retro',
	'Musical', 'Rock&Roll', 'HardRock', 'Folk', 'Folk-Rock', 'NationalFolk',
	'Swing', 'FastFusion', 'Bebob', 'Latin', 'Revival', 'Celtic', 'Bluegrass',
	'Avantgarde', 'GothicRock', 'ProgressiveRock', 'PsychedelicRock',
	'SymphonicRock', 'SlowRock', 'BigBand', 'Chorus', 'EasyListening',
	'Acoustic', 'Humor', 'Speech', 'Chanson', 'Opera', 'ChamberMusic',
	'Sonata', 'Symphony', 'BootyBass', 'Primus', 'PornGroove', 'Satire',
	'SlowJam', 'Club', 'Tango', 'Samba', 'Folklore', 'Ballad', 'PowerBallad',
	'RhythmicSoul', 'Freestyle', 'Duet', 'PunkRock', 'DrumSolo', 'Acapella',
	'Euro-House', 'DanceHall', 'Goa', 'Drum&Bass', 'Club-House', 'Hardcore',
	'Terror', 'Indie', 'BritPop', 'Negerpunk', 'PolskPunk', 'Beat',
	'ChristianGangstaRap', 'HeavyMetal', 'BlackMetal', 'Crossover',
	'ContemporaryChristian', 'ChristianRock', 'Merengue', 'Salsa',
	'ThrashMetal', 'Anime', 'J-Pop', 'Synthpop', 'Rock/Pop', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
	'Unknown', 'Unknown', 'Unknown', 'Unknown'
)
"""The venerable ID3v1 genres"""

ID3V2_TEXT_ENCODING = { 0: 'latin_1', 1: 'utf_16', 2: 'utf_16_be', 3: 'utf_8' }
"""ID3v2 text encoding lookup table"""
ID3V2_TEXT_TERMS = { 0: b'\x00', 1: b'\x00\x00', 2: b'\x00\x00', 3: b'\x00' }
"""ID3v2 string terminating byte(s) table"""


#
# ID3 tag functions
#


def decode_synchsafe_int( i ):
	"""Decode SynchSafe integers from ID3v2 tags"""
	i = int.from_bytes( i, 'big' )
	if i & 0x80808080:
		raise SyncError( 'Bad sync in SynchSafe integer!' )
	return ( ( i & 0xFF000000 ) >> 3 ) | ( ( i & 0x00FF0000 ) >> 2 ) | ( ( i & 0x0000FF00 ) >> 1 ) | ( i & 0x000000FF )


def encode_synchsafe_int( i ):
	"""Encode SynchSafe integers for ID3v2 tags"""
	return ( ( ( i & 0x0FE00000 ) << 3 ) | ( ( i & 0x001FC000 ) << 2 ) | ( ( i & 0x00003F80 ) << 1 ) | ( i & 0x0000007F ) ).to_bytes( 4, 'big' )


def read_id3v1( data ):
	"""Read ID3v1 tag if present and return the fields"""
	fields = dict()

	if len( data ) >= 128 and data[-128:-125] == b'TAG':
		if len( data ) >= 355 and data[-355:-351] == b'TAG+':
			titleLastSixty = data[-351:-291]
			artistLastSixty = data[-291:-231]
			albumLastSixty = data[-231:-171]
			genre = data[-170:-140].decode( 'ascii' ).rstrip( '\x00' )
		else:
			titleLastSixty = bytes()
			artistLastSixty = bytes()
			albumLastSixty = bytes()
			genre = str()

		title = ( data[-125:-95] + titleLastSixty ).decode( 'ascii' ).rstrip( ' \x00' )
		artist = ( data[-95:-65] + artistLastSixty ).decode( 'ascii' ).rstrip( ' \x00' )
		album = ( data[-65:-35] + albumLastSixty ).decode( 'ascii' ).rstrip( ' \x00' )
		year = data[-35:-31].decode( 'ascii' ).rstrip( ' \x00' )
		if data[-3] == 0:
			comment = data[-31:-3].decode( 'ascii' ).rstrip( ' \x00' )
			track = data[-2]
		elif data[-3] > 0x7F:
			comment = data[-31:-3].decode( 'ascii' ).rstrip( ' \x00' )
			track = 0
		else:
			comment = data[-31:-1].decode( 'ascii' ).rstrip( ' \x00' )
			track = 0
		if len( genre ) == 0:
			genre = ID3V1_GENRES[data[-1]]

		if len( title ) > 0:
			fields['title'] = title
		if len( artist ) > 0:
			fields['artist'] = artist
		if len( album ) > 0:
			fields['album'] = album
		if track > 0:
			fields['track'] = track
		if genre.upper() != 'UNKNOWN':
			fields['genre'] = genre
		if len( year ) > 0 and int( year ) > 0:
			fields['year'] = int( year )
		if len( comment ) > 0:
			fields['comment'] = comment

	return fields


def read_id3v2_data( data ):
	"""Read ID3v1 tag assuming it is present and return the fields"""
	assert len( data ) >= 10
	assert data[0:3] == b'ID3'
	assert data[3] == 2 or data[3] == 3 or data[3] == 4
	assert data[4] == 0

	fields = dict()

	if data[3] == 2:
		size = decode_synchsafe_int( data[6:10] ) + 10
		pos = 10

		while pos + 6 < size and data[pos] != 0:
			frame_size = int.from_bytes( data[pos+3:pos+6], 'big' )

			if data[pos:pos+3] == b'TT2':
				fields['title'] = data[pos+7:pos+6+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+6]] )
			elif data[pos:pos+3] == b'TP1':
				fields['artist'] = data[pos+7:pos+6+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+6]] )
			elif data[pos:pos+3] == b'TAL':
				fields['album'] = data[pos+7:pos+6+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+6]] )
			elif data[pos:pos+3] == b'TRK':
				fields['track'] = int( data[pos+7:pos+6+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+6]] ) )
			elif data[pos:pos+3] == b'TPA':
				fields['disc'] = int( data[pos+7:pos+6+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+6]] ) )
			elif data[pos:pos+3] == b'TCO':
				fields['genre'] = data[pos+7:pos+6+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+6]] )
			elif data[pos:pos+3] == b'TYE':
				fields['year'] = int( data[pos+7:pos+6+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+6]] ) )
			elif data[pos:pos+3] == b'COM':
				fields['comment'] = data[data.find( ID3V2_TEXT_TERMS[data[pos+6]], pos+10 ) + 1 : pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+6]] )
			elif data[pos:pos+3] == b'PIC':
				fields['cover'] = data[data.find( ID3V2_TEXT_TERMS[data[pos+6]], pos+11 ) + 1 : pos+10+frame_size]

			pos += frame_size + 6

	elif data[3] == 3 or data[3] == 4:
		size = decode_synchsafe_int( data[6:10] ) + 10
		if data[5] & 0x40:
			pos = 10 + decode_synchsafe_int( data[10:14] )
		else:
			pos = 10

		while pos + 10 <= size and data[pos] != 0:
			frame_size = int.from_bytes( data[pos+4:pos+8], 'big' )

			if data[pos:pos+4] == b'TIT2':
				fields['title'] = data[pos+11:pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+10]] )
			elif data[pos:pos+4] == b'TPE1':
				fields['artist'] = data[pos+11:pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+10]] )
			elif data[pos:pos+4] == b'TALB':
				fields['album'] = data[pos+11:pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+10]] )
			elif data[pos:pos+4] == b'TRCK':
				fields['track'] = int( data[pos+11:pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+10]] ) )
			elif data[pos:pos+4] == b'TPOS':
				fields['disc'] = int( data[pos+11:pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+10]] ) )
			elif data[pos:pos+4] == b'TCON':
				fields['genre'] = data[pos+11:pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+10]] )
				mat = re.match( '\((\d+)\)(\w+)', fields['genre'] )
				if mat and int( mat.group( 1 ) ) < 256 and ID3V1_GENRES[int( mat.group( 1 ) )] == mat.group( 2 ):
					fields['genre'] = mat.group( 2 )
			elif data[pos:pos+4] == b'TYER' or data[pos:pos+4] == b'TDRL' or data[pos:pos+4] == b'TDRC':
				fields['year'] = int( data[pos+11:pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+10]] ) )
			elif data[pos:pos+4] == b'COMM':
				fields['comment'] = data[data.find( ID3V2_TEXT_TERMS[data[pos+10]], pos+14 ) + len( ID3V2_TEXT_TERMS[data[pos+10]] ) : pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+10]] )
			elif data[pos:pos+4] == b'APIC':
				fields['cover'] = data[data.find( ID3V2_TEXT_TERMS[data[pos+10]], data.find( b'\x00', pos+11 ) + 2 ) + len( ID3V2_TEXT_TERMS[data[pos+10]] ) : pos+10+frame_size]
			elif data[pos:pos+4] == b'TDTG':
				fields['timestamp'] = data[pos+11:pos+10+frame_size].decode( ID3V2_TEXT_ENCODING[data[pos+10]] )

			pos += 10 + frame_size

	return fields


def read_id3v2_header( data ):
	"""Read IDv3 header if present and return the fields"""
	if len( data ) >= 10 and data[0:3] == b'ID3' and data[4] == 0:
		if data[3] == 2 or data[3] == 3:
			return read_id3v2_data( data[:10+decode_synchsafe_int( data[6:10] )] )
		elif data[3] == 4:
			if data[5] & 0x10:
				return read_id3v2_data( data[:20+decode_synchsafe_int( data[6:10] )] )
			else:
				return read_id3v2_data( data[:10+decode_synchsafe_int( data[6:10] )] )
	return dict()


def read_id3v2_footer( data ):
	"""Read IDv3 footer if present and return the fields"""
	pos = len( data ) - 10
	while pos > 0:
		if data[pos:pos+3] == b'ID3' and data[pos+4] == 0:
			if data[pos+3] == 2 or data[pos+3] == 3:
				return read_id3v2_data( data[pos:pos+10+decode_synchsafe_int( data[6:10] )] )
			elif data[pos+3] == 4:
				if data[5] & 0x10:
					return read_id3v2_data( data[pos:pos+20+decode_synchsafe_int( data[6:10] )] )
				else:
					return read_id3v2_data( data[pos:pos+10+decode_synchsafe_int( data[6:10] )] )
		pos -= 1
	return dict()


def remove_id3v1( data ):
	"""Remove ID3v1 tag if present"""
	if len( data ) >= 355:
		if data[-128:-125] == b'TAG':
			if data[-355:351] == b'TAG+':
				return data[0:-355]
			else:
				return data[0:-128]
	elif len( data ) >= 128:
		if data[-128:-125] == b'TAG':
			return data[0:-128]
	return data


def remove_id3v2_header( data ):
	"""Remove ID3v2 header tag if present"""
	if len( data ) >= 10 and data[0:3] == b'ID3' and data[4] == 0:
		if data[3] == 2 or data[3] == 3:
			return data[decode_synchsafe_int( data[6:10] )+10:]
		elif data[3] == 4:
			if data[5] & 0x10:
				return data[decode_synchsafe_int( data[6:10] )+20:]
			else:
				return data[decode_synchsafe_int( data[6:10] )+10:]
	return data


def remove_id3v2_footer( data ):
	"""Remove ID3v2 footer tag if present"""
	pos = len( data ) - 10
	while pos > 0:
		if data[pos:pos+3] == b'ID3' and data[pos+4] == 0:
			if data[pos+3] == 2 or data[pos+3] == 3:
				return data[:pos] + data[pos+decode_synchsafe_int( data[6:10] )+10:]
			elif data[pos+3] == 4:
				if data[pos+5] & 0x10:
					return data[:pos] + data[pos+decode_synchsafe_int( data[6:10] )+20:]
				else:
					return data[:pos] + data[pos+decode_synchsafe_int( data[6:10] )+10:]
		pos -= 1
	return data


def write_id3v2_header( data, fields ):
	"""Add an ID3v2 header to the data assuming none already present"""
	body = bytes()

	if 'title' in fields:
		title_bytes = b'\x03' + fields['title'].encode( 'utf_8' )
		body += b'TIT2' + len( title_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + title_bytes
	if 'artist' in fields:
		artist_bytes = b'\x03' + fields['artist'].encode( 'utf_8' )
		body += b'TPE1' + len( artist_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + artist_bytes
	if 'album' in fields:
		album_bytes = b'\x03' + fields['album'].encode( 'utf_8' )
		body += b'TALB' + len( album_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + album_bytes
	if 'track' in fields:
		track_bytes = b'\x00' + str( fields['track'] ).encode( 'latin_1' )
		body += b'TRCK' + len( track_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + track_bytes
	if 'disc' in fields:
		disc_bytes = b'\x00' + str( fields['disc'] ).encode( 'latin_1' )
		body += b'TPOS' + len( disc_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + disc_bytes
	if 'genre' in fields:
		genre_bytes = b'\x03' + fields['genre'].encode( 'utf_8' )
		body += b'TCON' + len( genre_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + genre_bytes
	if 'year' in fields:
		year_bytes = b'\x00' + str( fields['year'] ).encode( 'latin_1' )
		body += b'TYER' + len( year_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + year_bytes
	if 'comment' in fields:
		comment_bytes = b'\x03   \x00' + fields['comment'].encode( 'utf_8' )
		body += b'COMM' + len( comment_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + comment_bytes
	if 'cover' in fields:
		cover_bytes = b'\x00' + ( 'image/' + imghdr.what( '', h=fields['cover'] ) ).encode( 'latin_1' ) + b'\x00\x03\x00' + fields['cover']
		body += b'APIC' + len( cover_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + cover_bytes
	fields['timestamp'] = datetime.datetime.utcnow().replace( microsecond=0 ).isoformat()
	timestamp_bytes = b'\x00' + fields['timestamp'].encode( 'latin_1' )
	body += b'TDTG' + len( timestamp_bytes ).to_bytes( 4, 'big' ) + b'\x00\x00' + timestamp_bytes

	return b'ID3\x04\x00\x00' + encode_synchsafe_int( len( body ) ) + body + data


#
# METADATA_BLOCK_PICTURE functions
#


def read_metadatablockpicture( data ):
	"""Extract picture from a METADATA_BLOCK_PICTURE"""
	off = 8 + int.from_bytes( data[4:8], 'big' )
	off += 4 + int.from_bytes( data[off:off+4], 'big' ) + 16
	size = int.from_bytes( data[off:off+4], 'big' )
	return data[4+off:4+off+size]


def write_metadatablockpicture( picture_path ):
	"""Create a METADATA_BLOCK_PICTURE from a picture"""
	# Probe
	probe_out = subprocess.check_output( ( 'identify', '-verbose', picture_path ), stderr=subprocess.DEVNULL ).decode( errors='ignore' )
	# Picture type
	mbp = b'\x00\x00\x00\x03'
	# Picture MIME
	if probe_out.find( '  Format: JPEG' ) != -1:
		mbp += b'\x00\x00\x00\x0Aimage/jpeg'
	elif probe_out.find( '  Format: PNG' ) != -1:
		mbp += b'\x00\x00\x00\x09image/png'
	elif probe_out.find( '  Format: GIF' ) != -1:
		mbp += b'\x00\x00\x00\x09image/gif'
	else:
		mbp += b'\x00\x00\x00\x06image/'
	# Picture description
	mbp += b'\x00\x00\x00\x00'
	# Picture dimensions
	dim_mat = re.search( r'^  Geometry: (\d+)x(\d+)', probe_out, re.M )
	mbp += int( dim_mat.group( 1 ) ).to_bytes( 4, 'big' )
	mbp += int( dim_mat.group( 2 ) ).to_bytes( 4, 'big' )
	# Picture bits-per-pixel
	depth = 0
	mat = re.search( r'^    red: (\d+)-bit$', probe_out, re.M )
	if mat:
		depth += int( mat.group( 1 ) )
	mat = re.search( r'^    green: (\d+)-bit$', probe_out, re.M )
	if mat:
		depth += int( mat.group( 1 ) )
	mat = re.search( r'^    blue: (\d+)-bit$', probe_out, re.M )
	if mat:
		depth += int( mat.group( 1 ) )
	mat = re.search( r'^    alpha: (\d+)-bit$', probe_out, re.M )
	if mat:
		depth += int( mat.group( 1 ) )
	mbp += depth.to_bytes( 4, 'big' )
	# Number of colors (indexed pictures)
	mat = re.search( r'^  Colors: (\d+)$', probe_out, re.M )
	if mat:
		mbp += int( mat.group( 1 ) ).to_bytes( 4, 'big' )
	else:
		mbp += b'\x00\x00\x00\x00'
	# Picture data
	mbp += len( picture ).to_bytes( 4, 'big' )
	mbp += picture
	# Done
	return mbp


#
# Universal tag functions
#


def get_tag( path ):
	"""Get tag data from audio file"""
	ext = os.path.splitext( path )[1].lower()
	fields = dict()

	if ext == '.m4a':
		for line in subprocess.check_output( ( 'neroAacTag', path, '-list-meta' ), stderr=subprocess.DEVNULL ).decode().splitlines():
			mat = AAC_TITLE_RE.match( line )
			if mat:
				fields['title'] = mat.group( 1 )
				continue
			mat = AAC_ARTIST_RE.match( line )
			if mat:
				fields['artist'] = mat.group( 1 )
				continue
			mat = AAC_ALBUM_RE.match( line )
			if mat:
				fields['album'] = mat.group( 1 )
				continue
			mat = AAC_TRACK_RE.match( line )
			if mat:
				fields['track'] = int( mat.group( 1 ) )
				continue
			mat = AAC_DISC_RE.match( line )
			if mat:
				fields['disc'] = int( mat.group( 1 ) )
				continue
			mat = AAC_GENRE_RE.match( line )
			if mat:
				fields['genre'] = mat.group( 1 )
				continue
			mat = AAC_YEAR_RE.match( line )
			if mat:
				fields['year'] = int( mat.group( 1 ) )
				continue
			mat = AAC_COMMENT_RE.match( line )
			if mat:
				fields['comment'] = mat.group( 1 )
				continue
		if 'front cover' in subprocess.check_output( ( 'neroAacTag', path, '-list-covers' ), stderr=subprocess.DEVNULL ).decode():
			fields['cover'] = free_filename()
			subprocess.check_call( ( 'neroAacTag', path, '-dump-cover:front:' + fields['cover'] ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
	elif ext == '.flac':
		for line in subprocess.check_output( ( 'metaflac', '--list', '--block-type=VORBIS_COMMENT', path ), stderr=subprocess.DEVNULL ).decode().splitlines():
			mat = FLAC_TITLE_RE.match( line )
			if mat:
				fields['title'] = mat.group( 1 )
				continue
			mat = FLAC_ARTIST_RE.match( line )
			if mat:
				fields['artist'] = mat.group( 1 )
				continue
			mat = FLAC_ALBUM_RE.match( line )
			if mat:
				fields['album'] = mat.group( 1 )
				continue
			mat = FLAC_TRACK_RE.match( line )
			if mat:
				fields['track'] = int( mat.group( 1 ) )
				continue
			mat = FLAC_DISC_RE.match( line )
			if mat:
				fields['disc'] = int( mat.group( 1 ) )
				continue
			mat = FLAC_GENRE_RE.match( line )
			if mat:
				fields['genre'] = mat.group( 1 )
				continue
			mat = FLAC_YEAR_RE.match( line )
			if mat:
				fields['year'] = int( mat.group( 1 ) )
				continue
			mat = FLAC_COMMENT_RE.match( line )
			if mat:
				fields['comment'] = mat.group( 1 )
				continue
		if 'Cover (front)' in subprocess.check_output( ( 'metaflac', '--list', '--block-type=PICTURE', path ), stderr=subprocess.DEVNULL ).decode():
			fields['cover'] = free_filename()
			subprocess.check_call( ( 'metaflac', '--export-picture-to=' + fields['cover'], path ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
	elif ext == '.mp3':
		with open( path, 'rb' ) as input_file:
			input_data = input_file.read()
		fields.update( read_id3v1( input_data ) )
		fields.update( read_id3v2_header( input_data ) )
		fields.update( read_id3v2_footer( input_data ) )
		with open( free_filename() ) as cover_file:
			cover_file.write( fields['cover'] )
			fields['cover'] = cover_file.name
	elif ext == '.ogg':
		for line in subprocess.check_output( ( 'vorbiscomment', '--list', path ), stderr=subprocess.DEVNULL ).decode().splitlines():
			mat = VORBIS_TITLE_RE.match( line )
			if mat:
				fields['title'] = mat.group( 1 )
				continue
			mat = VORBIS_ARTIST_RE.match( line )
			if mat:
				fields['artist'] = mat.group( 1 )
				continue
			mat = VORBIS_ALBUM_RE.match( line )
			if mat:
				fields['album'] = mat.group( 1 )
				continue
			mat = VORBIS_TRACK_RE.match( line )
			if mat:
				fields['track'] = int( mat.group( 1 ) )
				continue
			mat = VORBIS_DISC_RE.match( line )
			if mat:
				fields['disc'] = int( mat.group( 1 ) )
				continue
			mat = VORBIS_GENRE_RE.match( line )
			if mat:
				fields['genre'] = mat.group( 1 )
				continue
			mat = VORBIS_YEAR_RE.match( line )
			if mat:
				fields['year'] = int( mat.group( 1 ) )
				continue
			mat = VORBIS_COMMENT_RE.match( line )
			if mat:
				fields['comment'] = mat.group( 1 )
				continue
			mat = VORBIS_COVER_RE.match( line )
			if mat:
				with open( free_filename() ) as cover_file:
					cover_file.write( read_metadatablockpicture( base64.b64decode( mat.group( 1 ) ) ) )
					fields['cover'] = cover_file.name
				continue
	elif ext == '.opus':
		for line in subprocess.check_output( ( 'opusinfo', path ), stderr=subprocess.DEVNULL ).decode().splitlines():
			mat = OPUS_TITLE_RE.match( line )
			if mat:
				fields['title'] = mat.group( 1 )
				continue
			mat = OPUS_ARTIST_RE.match( line )
			if mat:
				fields['artist'] = mat.group( 1 )
				continue
			mat = OPUS_ALBUM_RE.match( line )
			if mat:
				fields['album'] = mat.group( 1 )
				continue
			mat = OPUS_TRACK_RE.match( line )
			if mat:
				fields['track'] = int( mat.group( 1 ) )
				continue
			mat = OPUS_DISC_RE.match( line )
			if mat:
				fields['disc'] = int( mat.group( 1 ) )
				continue
			mat = OPUS_GENRE_RE.match( line )
			if mat:
				fields['genre'] = mat.group( 1 )
				continue
			mat = OPUS_YEAR_RE.match( line )
			if mat:
				fields['year'] = int( mat.group( 1 ) )
				continue
			mat = OPUS_COMMENT_RE.match( line )
			if mat:
				fields['comment'] = mat.group( 1 )
				continue
		# TODO Get Opus cover
	elif ext == '.wav':
		pass
	elif ext == '.wv':
		for line in subprocess.check_output( ( 'wvunpack', '-ss', path ), stderr=subprocess.DEVNULL ).decode().splitlines():
			mat = WAVPACK_TITLE_RE.match( line )
			if mat:
				fields['title'] = mat.group( 1 )
				continue
			mat = WAVPACK_ARTIST_RE.match( line )
			if mat:
				fields['artist'] = mat.group( 1 )
				continue
			mat = WAVPACK_ALBUM_RE.match( line )
			if mat:
				fields['album'] = mat.group( 1 )
				continue
			mat = WAVPACK_TRACK_RE.match( line )
			if mat:
				fields['track'] = int( mat.group( 1 ) )
				continue
			mat = WAVPACK_DISC_RE.match( line )
			if mat:
				fields['disc'] = int( mat.group( 1 ) )
				continue
			mat = WAVPACK_GENRE_RE.match( line )
			if mat:
				fields['genre'] = mat.group( 1 )
				continue
			mat = WAVPACK_YEAR_RE.match( line )
			if mat:
				fields['year'] = int( mat.group( 1 ) )
				continue
			mat = WAVPACK_COMMENT_RE.match( line )
			if mat:
				fields['comment'] = mat.group( 1 )
				continue
			mat = WAVPACK_COVER_RE.match( line )
			if mat:
				fields['cover'] = free_filename()
				subprocess.check_call( ( 'wvunpack', '-n', '-xx', 'Cover Art (Front)=' + fields['cover'] ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
				continue
	else:
		raise Exception( 'Reading tags from ' + ext + ' files is not supported.' )

	return fields


def set_tag( path, tag ):
	"""Set tag data in audio file"""
	ext = os.path.splitext( path )[1].lower()
	fields = dict()

	if ext == '.m4a':
		# Strip metadata
		subprocess.check_call( ( 'MP4Box', '-add', path, path, '-new' ) )
		# Add metadata
		tag_args = tuple()
		if 'title' in tag:
			tag_args += ( '-meta:title=' + tag['title'], )
		if 'artist' in tag:
			tag_args += ( '-meta:artist=' + tag['artist'], )
		if 'album' in tag:
			tag_args += ( '-meta:album=' + tag['album'], )
		if 'track' in tag:
			tag_args += ( '-meta:track=' + str( tag['track'] ), )
		if 'disc' in tag:
			tag_args += ( '-meta:disc=' + str( tag['disc'] ), )
		if 'genre' in tag:
			tag_args += ( '-meta:genre=' + tag['genre'], )
		if 'year' in tag:
			tag_args += ( '-meta:year=' + str( tag['year'] ), )
		if 'comment' in tag:
			tag_args += ( '-meta:comment=' + tag['comment'], )
		if 'cover' in tag:
			tag_args += ( '-add-cover:front:' + tag['cover'], )
		subprocess.check_call( ( 'neroAacTag', out_path ) + tag_args )
	elif ext == '.flac':
		# Strip metadata
		subprocess.check_call( ( 'metaflac', '--remove-all-tags', path ) )
		subprocess.check_call( ( 'metaflac', '--remove', '--block-type=PICTURE', path ) )
		# Add metadata
		tag_args = tuple()
		if 'title' in tag:
			tag_args += ( '--set-tag=TITLE=' + tag['title'], )
		if 'artist' in tag:
			tag_args += ( '--set-tag=ARTIST=' + tag['artist'], )
		if 'album' in tag:
			tag_args += ( '--set-tag=ALBUM=' + tag['album'], )
		if 'track' in tag:
			tag_args += ( '--set-tag=TRACKNUMBER=' + str( tag['track'] ), )
		if 'disc' in tag:
			tag_args += ( '--set-tag=DISCNUMBER=' + str( tag['disc'] ), )
		if 'genre' in tag:
			tag_args += ( '--set-tag=GENRE=' + tag['genre'], )
		if 'year' in tag:
			tag_args += ( '--set-tag=DATE=' + str( tag['year'] ), )
		if 'comment' in tag:
			tag_args += ( '--set-tag=COMMENT=' + tag['comment'], )
		if 'cover' in tag:
			tag_args += ( '--import-picture-from=' + tag['cover'], )
		subprocess.check_call( ( 'metaflac', ) + tag_args + ( path, ) )
	elif ext == '.mp3':
		with open( path, 'rb' ) as mp3_file:
			mp3_data = mp3_file.read()
		mp3_data = remove_id3v1( mp3_data )
		mp3_data = remove_id3v2_header( mp3_data )
		if len( tag ) > 0:
			if 'cover' in tag:
				with open( tag['cover'], 'rb' ) as cover_file:
					tag['cover'] = cover_file.read()
			mp3_data = write_id3v2_header( mp3_data, tag )
		with open( path, 'wb' ) as mp3_file:
			mp3_file.write( mp3_data )
	elif ext == '.ogg':
		# Set everything but cover
		tag_args = tuple()
		if 'title' in tag:
			tag_args += ( '--tag', 'TITLE=' + tag['title'] )
		if 'artist' in tag:
			tag_args += ( '--tag', 'ARTIST=' + tag['artist'] )
		if 'album' in tag:
			tag_args += ( '--tag', 'ALBUM=' + tag['album'] )
		if 'track' in tag:
			tag_args += ( '--tag', 'TRACKNUMBER=' + str( tag['track'] ) )
		if 'disc' in tag:
			tag_args += ( '--tag', 'DISCNUMBER=' + str( tag['disc'] ) )
		if 'genre' in tag:
			tag_args += ( '--tag', 'GENRE=' + tag['genre'] )
		if 'year' in tag:
			tag_args += ( '--tag', 'DATE=' + str( tag['year'] ) )
		if 'comment' in tag:
			tag_args += ( '--tag', 'COMMENT=' + tag['comment'] )
		subprocess.check_call( ( 'vorbiscomment', '--write', tag_args, path ) )
		# Set cover
		if 'cover' in tag:
			with tempfile.NamedTemporaryFile( suffix='.tmp', dir=tmpdir.name ) as vcf:
				vcf.write( b'METADATA_BLOCK_PICTURE=' )
				vcf.write( base64.b64encode( write_metadatablockpicture( tag['cover'] ) ) )
				vcf.write( b'\n' )
				vcf.flush()
				subprocess.check_call( ( 'vorbiscomment', '-a', out_path, '-c', vcf.name ) )
	elif ext == '.opus':
		raise Exception( 'Setting tags in ' + ext + ' files is not supported!' )
	elif ext == '.wav':
		raise Exception( 'Setting tags in ' + ext + ' files is not supported!' )
	elif ext == '.wv':
		raise Exception( 'Setting tags in ' + ext + ' files is not supported!' )
	else:
		raise Exception( 'Setting tags in ' + ext + ' files is not supported!' )


#
# Audio codec functions
#


def convert_audio_format( in_path, out_path, tag=dict() ):
	# Format check
	in_ext = os.path.splitext( in_path )[1].lower()
	out_ext = os.path.splitext( out_path )[1].lower()
	if in_ext not in FORMAT_EXT_MAP.values():
		raise Exception( 'The ' + in_ext + ' format is not supported and cannot be decoded.' )
	if out_ext not in FORMAT_EXT_MAP.values():
		raise Exception( 'The ' + out_ext + ' format is not supported and cannot be encoded.' )

	# Setup decode process
	if in_ext == '.m4a':
		dec_proc = subprocess.Popen( ( 'neroAacDec', '-if', in_path, '-of', '-' ), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL )
	elif in_ext == '.flac':
		dec_proc = subprocess.Popen( ( 'flac', '--decode', '--stdout', in_path ), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL )
	elif in_ext == '.mp3':
		dec_proc = subprocess.Popen( ( 'lame', '--decode', in_path, '-' ), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL )
	elif in_ext == '.opus':
		dec_proc = subprocess.Popen( ( 'opusdec', in_path, '-' ), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL )
	elif in_ext == '.ogg':
		dec_proc = subprocess.Popen( ( 'oggdec',  '--output=-', in_path ), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL )
	elif in_ext == '.wav':
		dec_proc = subprocess.Popen( ( 'cat', in_path ), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL )
	elif in_ext == '.wv':
		dec_proc = subprocess.Popen( ( 'wvunpack', in_path, '-o', '-' ), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL )
	else:
		assert False

	# Setup encode process
	if out_ext == '.m4a':
		if shutil.which( 'ffmpeg' ) is not None:
			tag_args = tuple()
			if 'title' in tag:
				tag_args += ( '-metadata', 'title=' + tag['title'] )
			if 'artist' in tag:
				tag_args += ( '-metadata', 'artist=' + tag['artist'] )
			if 'album' in tag:
				tag_args += ( '-metadata', 'album=' + tag['album'] )
			if 'track' in tag:
				tag_args += ( '-metadata', 'track=' + str( tag['track'] ) )
			if 'disc' in tag:
				tag_args += ( '-metadata', 'disc=' + str( tag['disc'] ) )
			if 'genre' in tag:
				tag_args += ( '-metadata', 'genre=' + tag['genre'] )
			if 'year' in tag:
				tag_args += ( '-metadata', 'year=' + str( tag['year'] ) )
			if 'comment' in tag:
				tag_args += ( '-metadata', 'comment=' + tag['comment'] )
			enc_proc = subprocess.Popen( ( 'ffmpeg', '-i', '-', '-strict', 'experimental' ) + tag_args + ( '-c:a', 'aac', '-q:a', '1.5', out_path ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
		elif shutil.which( 'fdkaac' ) is not None:
			tag_args = tuple()
			if 'title' in tag:
				tag_args += ( '--title', tag['title'] )
			if 'artist' in tag:
				tag_args += ( '--artist', tag['artist'] )
			if 'album' in tag:
				tag_args += ( '--album', tag['album'] )
			if 'track' in tag:
				tag_args += ( '--track', str( tag['track'] ) )
			if 'disc' in tag:
				tag_args += ( '--disk', str( tag['disc'] ) )
			if 'genre' in tag:
				tag_args += ( '--genre', tag['genre'] )
			if 'year' in tag:
				tag_args += ( '--date', str( tag['year'] ) )
			if 'comment' in tag:
				tag_args += ( '--comment', tag['comment'] )
			if 'cover' in tag:
				tag_args += ( '--tag-from-file', 'covr:' + tag['cover'] )
			enc_proc = subprocess.Popen( ( 'fdkaac', '-m', '4' ) + tag_args + ( '-o', out_path, '-' ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
		elif shutil.which( 'neroAacEnc' ) is not None:
			enc_proc = subprocess.Popen( ( 'neroAacEnc', '-ignorelength', '-q', '0.4', '-if', '-', '-of', out_path ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
		elif shutil.which( 'faac' ) is not None:
			tag_args = tuple()
			if 'title' in tag:
				tag_args += ( '--title', tag['title'] )
			if 'artist' in tag:
				tag_args += ( '--artist', tag['artist'] )
			if 'album' in tag:
				tag_args += ( '--album', tag['album'] )
			if 'track' in tag:
				tag_args += ( '--track', str( tag['track'] ) )
			if 'disc' in tag:
				tag_args += ( '--disc', str( tag['disc'] ) )
			if 'genre' in tag:
				tag_args += ( '--genre', tag['genre'] )
			if 'year' in tag:
				tag_args += ( '--year', str( tag['year'] ) )
			if 'comment' in tag:
				tag_args += ( '--comment', tag['comment'] )
			if 'cover' in tag:
				tag_args += ( '--cover-art', tag['cover'] )
			enc_proc = subprocess.Popen( ( 'faac', ) + tag_args + ( '-o', out_path, '-' ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
		else:
			raise Exception( 'No suitable AAC compressor found!' )
	elif out_ext == '.flac':
		tag_args = tuple()
		if 'title' in tag:
			tag_args += ( '--tag=TITLE=' + tag['title'], )
		if 'artist' in tag:
			tag_args += ( '--tag=ARTIST=' + tag['artist'], )
		if 'album' in tag:
			tag_args += ( '--tag=ALBUM=' + tag['album'], )
		if 'track' in tag:
			tag_args += ( '--tag=TRACKNUMBER=' + str( tag['track'] ), )
		if 'disc' in tag:
			tag_args += ( '--tag=DISCNUMBER=' + str( tag['disc'] ), )
		if 'genre' in tag:
			tag_args += ( '--tag=GENRE=' + tag['genre'], )
		if 'year' in tag:
			tag_args += ( '--tag=DATE=' + str( tag['year'] ), )
		if 'comment' in tag:
			tag_args += ( '--tag=COMMENT=' + tag['comment'], )
		if 'cover' in tag:
			tag_args += ( '--picture=' + tag['cover'], )
		enc_proc = subprocess.Popen( ( 'flac', '--best' ) + tag_args + ( '--output-name=' + out_path, '-' ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
	elif out_ext == '.mp3':
		tag_args = tuple()
		if 'title' in tag:
			tag_args += ( '--tt', tag['title'] )
		if 'artist' in tag:
			tag_args += ( '--ta', tag['artist'] )
		if 'album' in tag:
			tag_args += ( '--tl', tag['album'] )
		if 'track' in tag:
			tag_args += ( '--tn', str( tag['track'] ) )
		if 'disc' in tag:
			tag_args += ( '--tv', 'TPOS=' + str( tag['disc'] ) )
		if 'genre' in tag:
			tag_args += ( '--tg', tag['genre'] )
		if 'year' in tag:
			tag_args += ( '--ty', str( tag['year'] ) )
		if 'comment' in tag:
			tag_args += ( '--tc', tag['comment'] )
		if 'cover' in tag:
			tag_args += ( '--ti', tag['cover'] )
		enc_proc = subprocess.Popen( ( 'lame', '-V', '0' ) + tag_args + ( '-', out_path ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
	elif out_ext == '.opus':
		tag_args = tuple()
		if 'title' in tag:
			tag_args += ( '--title', tag['title'] )
		if 'artist' in tag:
			tag_args += ( '--artist', tag['artist'] )
		if 'album' in tag:
			tag_args += ( '--album', tag['album'] )
		if 'track' in tag:
			tag_args += ( '--comment', 'tracknumber=' + str( tag['track'] ) )
		if 'disc' in tag:
			tag_args += ( '--comment', 'discnumber=' + str( tag['disc'] ) )
		if 'genre' in tag:
			tag_args += ( '--genre', tag['genre'] )
		if 'year' in tag:
			tag_args += ( '--date', str( tag['year'] ) )
		if 'comment' in tag:
			tag_args += ( '--comment', 'comment=' + tag['comment'] )
		if 'cover' in tag:
			if imghdr.what( tag['cover'] ) == 'jpeg':
				tag_args += ( '--picture', '|image/jpeg|||' + tag['cover'] )
			else:
				tag_args += ( '--picture', tag['cover'] )
		enc_proc = subprocess.Popen( ( 'opusenc', ) + tag_args + ( '-', out_path ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
	elif out_ext == '.ogg':
		tag_args = tuple()
		if 'title' in tag:
			tag_args += ( '--title', tag['title'] )
		if 'artist' in tag:
			tag_args += ( '--artist', tag['artist'] )
		if 'album' in tag:
			tag_args += ( '--album', tag['album'] )
		if 'track' in tag:
			tag_args += ( '--tracknum', str( tag['track'] ) )
		if 'disc' in tag:
			tag_args += ( '--comment', 'discnumber=' + str( tag['disc'] ) )
		if 'genre' in tag:
			tag_args += ( '--genre', tag['genre'] )
		if 'year' in tag:
			tag_args += ( '--date', str( tag['year'] ) )
		if 'comment' in tag:
			tag_args += ( '--comment', 'comment=' + tag['comment'] )
		enc_proc = subprocess.Popen( ( 'oggenc', ) + tag_args + ( '--output=' + out_path, '-' ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
		# Add cover later
	elif out_ext == '.wav':
		enc_proc = subprocess.Popen( ( 'tee', out_path ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
	elif out_ext == '.wv':
		tag_args = tuple()
		if 'title' in tag:
			tag_args += ( '-w', 'Title=' + tag['title'] )
		if 'artist' in tag:
			tag_args += ( '-w', 'Artist=' + tag['artist'] )
		if 'album' in tag:
			tag_args += ( '-w', 'Album=' + tag['album'] )
		if 'track' in tag:
			tag_args += ( '-w', 'Track=' + str( tag['track'] ) )
		if 'disc' in tag:
			tag_args += ( '-w', 'Disc=' + str( tag['disc'] ) )
		if 'genre' in tag:
			tag_args += ( '-w', 'Genre=' + tag['genre'] )
		if 'year' in tag:
			tag_args += ( '-w', 'Year=' + str( tag['year'] ) )
		if 'comment' in tag:
			tag_args += ( '-w', 'Comment=' + tag['comment'] )
		if 'cover' in tag:
			cover_file.write( tag['cover'] )
			tag_args += ( '--write-binary-tag', 'Cover Art (Front)=@' + cover_file.name )
			cover_file.flush()
		enc_proc = subprocess.Popen( ( 'wavpack', ) + tag_args + ( '-', '-o', out_path ), stdin=dec_proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
	else:
		assert False

	# Wait for decoding/encoding to finish
	dec_proc.stdout.close()
	if dec_proc.wait():
		raise Exception( 'Error occurred in ' + in_ext + ' decoding process.' )
	if enc_proc.wait():
		raise Exception( 'Error occurred in ' + out_ext + ' encoding process.' )

	if out_ext == '.m4a':
		if shutil.which( 'ffmpeg' ) is not None:
			if 'cover' in tag:
				subprocess.check_call( ( 'MP4Box', '-itags', 'cover=' + tag['cover'], out_path ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
		elif shutil.which( 'fdkaac' ) is not None:
			pass
		elif shutil.which( 'neroAacTag' ) is not None:
			tag_args = tuple()
			if 'title' in tag:
				tag_args += ( '-meta:title=' + tag['title'], )
			if 'artist' in tag:
				tag_args += ( '-meta:artist=' + tag['artist'], )
			if 'album' in tag:
				tag_args += ( '-meta:album=' + tag['album'], )
			if 'track' in tag:
				tag_args += ( '-meta:track=' + str( tag['track'] ), )
			if 'disc' in tag:
				tag_args += ( '-meta:disc=' + str( tag['disc'] ), )
			if 'genre' in tag:
				tag_args += ( '-meta:genre=' + tag['genre'], )
			if 'year' in tag:
				tag_args += ( '-meta:year=' + str( tag['year'] ), )
			if 'comment' in tag:
				tag_args += ( '-meta:comment=' + tag['comment'], )
			if 'cover' in tag:
				tag_args += ( '-add-cover:front:' + tag['cover'], )

	if out_ext == '.ogg' and 'cover' in tag:
		with tempfile.NamedTemporaryFile( suffix='.tmp', dir=tmpdir.name ) as vcf:
			vcf.write( b'METADATA_BLOCK_PICTURE=' )
			vcf.write( base64.b64encode( write_metadatablockpicture( tag['cover'] ) ) )
			vcf.write( b'\n' )
			vcf.flush()
			subprocess.check_call( ( 'vorbiscomment', '-a', out_path, '-c', vcf.name ) )


#
# Program entry point
#


def main( argv=None ):
	process_start_time = time.time()

	# Parse command line
	command_line_parser = argparse.ArgumentParser( description='simple audio manipulator' )
	command_line_parser.add_argument( '-x', '--transcode', choices=FORMAT_EXT_MAP.keys(), help='transcode to a different format' )
	command_line_parser.add_argument( '-r', '--recursive', action='store_true', help='allow directory input' )
	command_line_parser.add_argument( '-f', '--force', action='store_true', help='allows output to overwrite input' )
	command_line_parser.add_argument( 'infile', metavar='INFILE' )
	command_line_parser.add_argument( 'outfile', nargs='?', metavar='OUTFILE', help='set new result location' )

	command_line_tag_group = command_line_parser.add_argument_group( 'tag' )
	command_line_tag_group.add_argument( '-d', '--discard', action='store_true', help='discard existing tag data' )
	command_line_tag_group.add_argument( '-t', '--title', help='set title field', metavar='STRING' )
	command_line_tag_group.add_argument( '-a', '--artist', help='set artist field', metavar='STRING' )
	command_line_tag_group.add_argument( '-A', '--album', help='set album field', metavar='STRING' )
	command_line_tag_group.add_argument( '-T', '--track', type=int, help='set track number field', metavar='INT' )
	command_line_tag_group.add_argument( '-D', '--disc', type=int, help='set disc number field', metavar='INT' )
	command_line_tag_group.add_argument( '-g', '--genre', help='set genre field', metavar='STRING' )
	command_line_tag_group.add_argument( '-y', '--year', type=int, help='set year field', metavar='INT' )
	command_line_tag_group.add_argument( '-c', '--comment', help='set comment field', metavar='STRING' )
	command_line_tag_group.add_argument( '-C', '--cover', help='set cover art field', metavar='FILENAME' )

	command_line_other_group = command_line_parser.add_argument_group( 'other' )
	command_line_other_group.add_argument( '--no-nice', action='store_true', help='do not lower process priority' )

	if argv is None:
		command_line = command_line_parser.parse_args()
	else:
		command_line = command_line_parser.parse_args( argv )

	# Check for existing input
	if not os.path.exists( command_line.infile ):
		print( 'ERROR: No file at input path!' )
		return 1

	# Check for same input and output
	if command_line.outfile is not None and os.path.exists( command_line.outfile ) and os.path.samefile( command_line.infile, command_line.outfile ):
		print( 'ERROR: Input and output paths cannot be the same. (Omit second parameter for in-place editing.)' )
		return 1

	# Check for directory
	if os.path.isdir( command_line.infile ) and not command_line.recursive:
		print( 'ERROR: For security --recursive must be used on directory inputs!' )
		return 1
	if command_line.outfile is not None and os.path.exists( command_line.outfile ) and ( os.path.isdir( command_line.infile ) != os.path.isdir( command_line.outfile ) ):
		print( 'ERROR: Cannot mix files and directories!' )
		return 1

	# Don't overwrite existing files
	if command_line.outfile is not None and os.path.isfile( command_line.outfile ) and not command_line.force:
		print( 'ERROR: File exists at output path!' )
		return 1

	# Reduce priority
	if not command_line.no_nice:
		os.nice( 10 )

	# Gather new tag fields
	new_tag = dict()
	if command_line.title is not None:
		new_tag['title'] = command_line.title
	if command_line.artist is not None:
		new_tag['artist'] = command_line.artist
	if command_line.album is not None:
		new_tag['album'] = command_line.album
	if command_line.track is not None:
		new_tag['track'] = command_line.track
	if command_line.disc is not None:
		new_tag['disc'] = command_line.disc
	if command_line.genre is not None:
		new_tag['genre'] = command_line.genre
	if command_line.year is not None:
		new_tag['year'] = command_line.year
	if command_line.comment is not None:
		new_tag['comment'] = command_line.comment
	if command_line.cover is not None:
		new_tag['cover'] = command_line.cover

	# Execute/generate main task
	with concurrent.futures.ThreadPoolExecutor( multiprocessing.cpu_count() ) as executor:
		jobs = list()
		if command_line.outfile is None:
			# inplace
			if os.path.isfile( command_line.infile ):
				# non recursive
				tag = get_tag( command_line.infile )
				tag.update( new_tag )
				tag = { k:v for k, v in tag.items() if ( v != 0 or len( v ) > 0 ) }
				if command_line.transcode is None:
					# don't transcode
					set_tag( command_line.infile, tag )
				else:
					# transcode
					new_path = os.path.splitext( command_line.infile )[0] + FORMAT_EXT_MAP[command_line.transcode]
					if not os.path.exists( new_path ) or command_line.force:
						jobs.append( executor.submit( convert_audio_format, command_line.infile, new_path, tag ) )
					else:
						print( 'WARNING: Cannot overwrite ("', new_path, '") existing file without --force.  Cancelling...', sep=str() )
			else:
				# recursive
				for dirname, dirnames, filenames in os.walk( command_line.infile ):
					for filename in filenames:
						path = os.path.join( dirname, filename )
						head, tail = os.path.splitext( path )
						if tail.lower() in FORMAT_EXT_MAP.values():
							tag = get_tag( path )
							tag.update( new_tag )
							tag = { k:v for k, v in tag.items() if ( v != 0 or len( v ) > 0 ) }
							if command_line.transcode is None:
								# don't transcode
								set_tag( path, tag )
							else:
								# transcode
								new_path = head + FORMAT_EXT_MAP[command_line.transcode]
								if not os.path.exists( new_path ) or command_line.force:
									jobs.append( executor.submit( convert_audio_format, path, new_path, tag ) )
								else:
									print( 'WARNING: Cannot overwrite ("', new_path, '") existing file without --force.  Skipping...', sep=str() )
		else:
			# new file
			if os.path.isfile( command_line.infile ):
				# non recursive
				tag = get_tag( command_line.infile )
				tag.update( new_tag )
				tag = { k:v for k, v in tag.items() if ( v != 0 or len( v ) > 0 ) }
				if command_line.transcode is None and os.path.splitext( command_line.infile )[1].lower() == os.path.splitext( command_line.outfile )[1].lower():
					# don't transcode
					if not os.path.exists( command_line.outfile ) or command_line.force:
						shutil.copy( command_line.infile, command_line.outfile )
						set_tag( command_line.outfile, tag )
					else:
						print( 'WARNING: Cannot overwrite ("', command_line.outfile, '") existing file without --force.  Skipping...', sep=str() )
				else:
					# transcode
					if not os.path.exists( command_line.outfile ) or command_line.force:
						jobs.append( executor.submit( convert_audio_format, command_line.infile, command_line.outfile, tag ) )
					else:
						print( 'WARNING: Cannot overwrite ("', command_line.outfile, '") existing file without --force.  Cancelling...', sep=str() )
			else:
				# recursive
				if command_line.transcode is None:
					# don't transcode
					for old_dirpath, dirnames, filenames in os.walk( command_line.infile ):
						new_dirpath = os.path.normpath( os.path.join( command_line.outfile, os.path.relpath( old_dirpath, command_line.infile ) ) )
						if not os.path.exists( new_dirpath ):
							os.mkdir( new_dirpath )
						for filename in filenames:
							old_path = os.path.join( old_dirpath, filename )
							new_path = os.path.join( new_dirpath, filename )
							tag = get_tag( old_path )
							tag.update( new_tag )
							tag = { k:v for k, v in tag.items() if ( v != 0 or len( v ) > 0 ) }
							if not os.path.exists( new_path ) or command_line.force:
								shutil.copy( old_path, new_path )
								set_tag( new_path, tag )
							else:
								print( 'WARNING: Cannot overwrite ("', new_path, '") existing file without --force.  Skipping...', sep=str() )
				else:
					# transcode
					for old_dirpath, dirnames, filenames in os.walk( command_line.infile ):
						new_dirpath = os.path.normpath( os.path.join( command_line.outfile, os.path.relpath( old_dirpath, command_line.infile ) ) )
						if not os.path.exists( new_dirpath ):
							os.mkdir( new_dirpath )
						for filename in filenames:
							old_path = os.path.join( old_dirpath, filename )
							new_path = os.path.join( new_dirpath, os.path.splitext( filename )[0] + FORMAT_EXT_MAP[command_line.transcode] )
							tag = get_tag( old_path )
							tag.update( new_tag )
							tag = { k:v for k, v in tag.items() if ( v != 0 or len( v ) > 0 ) }
							if not os.path.exists( new_path ) or command_line.force:
								jobs.append( executor.submit( convert_audio_format, old_path, new_path, tag ) )
							else:
								print( 'WARNING: Cannot overwrite ("', new_path, '") existing file without --force.  Skipping...', sep=str() )

		counter = 0
		for job in concurrent.futures.as_completed( jobs ):
			counter += 1
			time_left = round( ( time.time() - process_start_time ) / counter * len( jobs ) - ( time.time() - process_start_time ) )
			print( 'Progress =', counter, '/', len( jobs ), ';', 'about', str( time_left // 3600 ).zfill( 1 ) + ':' + str( time_left // 60 % 60 ).zfill( 2 ) + ':' + str( time_left % 60 ).zfill( 2 ), 'left', flush=True )

	# Done
	process_time = round( time.time() - process_start_time )
	print( 'Finished. Process took', process_time // 3600, 'hours,', process_time // 60 % 60, 'minutes, and', process_time % 60, 'seconds.' )
	return 0

if __name__ == '__main__':
	sys.exit( main() )

# vim: ts=4:sw=4:noet:si
