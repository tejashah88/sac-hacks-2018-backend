'use strict'

const axios = require('axios');
const cheerio = require('cheerio')

async function getAgreementPage(origin, destination, major) {
    const html = await axios.get(`http://web2.assist.org/cgi-bin/REPORT_2/Rep2.pl?ia=${origin}&oia=${destination}&sia=${origin}&ria=${destination}&dora=${major}&aay=16-17&ay=16-17&event=19&agreement=aa&dir=1&sidebar=false&rinst=left&mver=2&kind=5&dt=2`);
    const $ = cheerio.load(html.data);
    return parseAgreement($('pre').text());
}

let isLineOrHeader = function (line) {
    line = line.toLowerCase()
    let tests = [
        function (line) { return line.match(/(from).*(list)/) },
        function (line) { return line.match(/(following).*(groups)/) }
    ]
    for (let test of tests) { if (test(line)) return true }
}
let isLineRecommendedHeader = function (line) {
    line = line.toLowerCase()
    let tests = [
        function (line) { return line.match(/strongly recommended/) }
    ]
    for (let test of tests) { if (test(line)) return true }
}
let collapseWhitespace = function (string) {
    return string.replace(/\s+/g, ' ')
}

let splitAgreementToGroupStreams = function (agreement) {
    let lines = agreement.substring(agreement.indexOf('|') - 41).split('\n')
    let plan = { required: [] }
    let output = plan.required
    for (let line of lines) {
        if (!line.match(/\|/)) {
            if (isLineOrHeader(line)) {
                plan.or = []
                output = plan.or
            }
            if (isLineRecommendedHeader(line)) {
                plan.recommended = []
                output = plan.recommended
            }
            continue
        }
        output.push(line)
    }
    return plan
}
let sortStreamsByBlock = function (plan) {
    for (let group in plan) {
        let output = []
        let buffer = { origin: [], destination: [] }
        let linked = { origin: false, destination: false }
        let flush = function () {
            if (buffer.origin.length && buffer.destination.length) {
                output.push({
                    origin: { raw: buffer.origin },
                    destination: { raw: buffer.destination }
                })
                buffer = { origin: [], destination: [] }
                linked = { origin: false, destination: false }
            }
        }
        for (let line of plan[group]) {
            let string = {
                origin: line.match(/[^|]*$/)[0],
                destination: line.match(/^(.*)(?=\|)/)[0]
            }
            if (string.origin.match(/\([0-9]\)/) ||
                    string.destination.match(/\([0-9]\)/)) {
                if (!linked.origin && !linked.destination) flush()
            }
            if (string.origin.match(/\([0-9]\)/)) {
                linked = { origin: false, destination: false }
            }
            if (string.destination.match(/\([0-9]\)/)) {
                linked = { origin: false, destination: false }
            }
            if (string.origin.match(/(\s\sOR)|(\s\sAND)|([0-Z]\s*&\s*[0-Z])/)) {
                linked.origin = true
            }
            if (string.destination.match(/(\s\sOR)|(\s\sAND)|([0-Z]\s*&\s*[0-Z])/)) {
                linked.destination = true
            }
            buffer.origin.push(string.origin.replace(/\r/g, ''))
            buffer.destination.push(string.destination.replace(/\r/g, ''))
        }
        flush()
        plan[group] = output
    }
}
let parseAnd = function (plan) {
    for (let group in plan) {
        for (let i = 0; i < plan[group].length; i++) {
            let block = plan[group][i]
            if (block.origin.raw.join('').match(/\s\sAND/)) {
                let output = { relation: 'parallel and', parts: [] }
                let buffer = { origin: [], destination: [] }
                let flush = function () {
                    output.parts.push({
                        origin: { raw: buffer.origin },
                        destination: { raw: buffer.destination }
                    })
                    buffer = { origin: [], destination: [] }
                }
                for (let i = 0; i < block.origin.raw.length; i++) {
                    if (block.origin.raw[i].match(/\s\sAND/)) {
                        flush()
                        continue
                    }
                    buffer.origin.push(block.origin.raw[i])
                    buffer.destination.push(block.destination.raw[i])
                }
                flush()
                plan[group][i] = output
            }
        }
    }
}
let parseOr = function (group) {
    for (let key in group) {
        if (typeof group[key] === 'object') {
            if (group[key].hasOwnProperty('origin')) {
                let block = group[key]
                if (block.origin.raw.join('').match(/\s\sOR/)) {
                    let isParallel = block.destination.raw.join('').match(/\s\sOR/)
                    let output = (isParallel)
                        ? { relation: 'parallel or', parts: [] }
                        : { origin: { relation: 'or', parts: [] }, destination: block.destination }
                    let buffer = (isParallel) ? { origin: [], destination: [] } : []
                    let flush = function () {
                        if (isParallel) {
                            output.parts.push({
                                origin: { raw: buffer.origin },
                                destination: { raw: buffer.destination }
                            })
                            buffer = { origin: [], destination: [] }
                        } else {
                            output.origin.parts.push({ origin: { raw: buffer } })
                            buffer = []
                        }
                    }
                    for (let i = 0; i < block.origin.raw.length; i++) {
                        if (block.origin.raw[i].match(/\s\sOR/)) {
                            flush()
                            continue
                        }
                        if (isParallel) {
                            buffer.origin.push(block.origin.raw[i])
                            buffer.destination.push(block.destination.raw[i])
                        } else buffer.push(block.origin.raw[i])
                    }
                    flush()
                    group[key] = output
                }
            } else parseOr(group[key])
        }
    }
}
let parseAmpersand = function (plan) {
    for (let key in plan) {
        if (typeof plan[key] === 'object') {
            if (plan[key].hasOwnProperty('raw')) {
                if (plan[key].raw.join('').match(/[0-Z]\s*&\s*[0-Z]/)) {
                    let side = plan[key].raw
                    let output = { relation: 'and', parts: [] }
                    let buffer = []
                    let flush = function () {
                        if (buffer.length) {
                            (key === 'origin')
                                ? output.parts.push({ origin: { raw: buffer } })
                                : output.parts.push({ destination: { raw: buffer } })
                            buffer = []
                        }
                    }
                    for (let line of side) {
                        if (line.match(/\([0-9]\)/)) {
                            flush()
                        }
                        buffer.push(line)
                    }
                    flush()
                    plan[key] = output
                }
            } else parseAmpersand(plan[key])
        }
    }
}
let parseCourses = function (plan) {
    for (let key in plan) {
        if (typeof plan[key] === 'object') {
            if (plan[key].hasOwnProperty('raw')) {
                let side = plan[key].raw.join(' ')
                if (side.toLowerCase().match(/no course articulated/)) {
                    plan[key] = { articulated: false }
                    continue
                }
                if (!side.match(/\([0-9]\)/)) {
                    plan[key] = { valid: false, text: collapseWhitespace(side).trim() }
                    continue
                }
                let output = { id: '', name: '', units: 0 }
                if (side.match(/[0-Z]\s*&\s*[0-Z]/)) side = side.replace(/&/, ' ')
                output.id = side.match(/([0-Z\s]*)\s\s/)[0].trim()
                side = side.substring(output.id.length)
                output.units = parseInt(side.match(/\([0-9]\)/)[0].replace(/[()]/g, ''))
                side = side.replace(/\([0-9]\)/, '')
                output.name = collapseWhitespace(side).trim()
                plan[key] = output
            } else parseCourses(plan[key])
        }
    }
}
let combineOrAndRequiredGroups = function (plan) {
    let output = { relation: 'parallel or', parts: [] }
    for (let block of plan.or) {
        if (JSON.stringify(block).match(/\s\sOR/)) {
            let wrapper = { value: block }
            parseOr(wrapper)
            block = wrapper.value
        }
        output.parts.push(block)
    }
    plan.required.push(output)
    delete plan.or
}

function parseAgreement(agreement) {
    let plan = splitAgreementToGroupStreams(agreement)
    sortStreamsByBlock(plan)
    parseAnd(plan)
    if (plan.required) parseOr(plan.required)
    if (plan.recommended) parseOr(plan.recommended)
    if (plan.or) combineOrAndRequiredGroups(plan)
    parseAmpersand(plan)
    parseCourses(plan)
    return plan
}

getAgreementPage(process.argv[2], process.argv[3], process.argv[4])
    .then(JSON.stringify)
    .then(console.log);