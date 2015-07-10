#ifndef URL_HPP
#define URL_HPP
/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

#include "proton/proton_handle.hpp"
#include "proton/error.hpp"
#include <iosfwd>

struct pn_url_t;

namespace proton {

struct bad_url : public error { PN_CPP_EXTERN explicit bad_url(const std::string&) throw(); };


/**
 * url is a proton URL of the form <scheme>://<username>:<password>@<host>:<port>/<path>.
 */
class url {
  public:
    static const std::string AMQP;     ///< "amqp" prefix
    static const std::string AMQPS;    ///< "amqps" prefix

    /** Create an empty url */
    PN_CPP_EXTERN url();

    /** Parse url_str as an AMQP URL. If defaults is true, fill in defaults for missing values
     *  otherwise return an empty string for missing values.
     *  Note: converts automatically from string.
     *@throws bad_url if URL is invalid.
     */
    PN_CPP_EXTERN url(const std::string& url_str, bool defaults=true);

    PN_CPP_EXTERN url(const url&);
    PN_CPP_EXTERN ~url();
    PN_CPP_EXTERN url& operator=(const url&);

    /** Parse a string as a URL 
     *@throws bad_url if URL is invalid.
     */
    PN_CPP_EXTERN void parse(const std::string&);

    PN_CPP_EXTERN bool empty() const;

    /** str returns the URL as a string string */
    PN_CPP_EXTERN std::string str() const;

    /**@name Get parts of the URL
     *@{
     */
    PN_CPP_EXTERN std::string scheme() const;
    PN_CPP_EXTERN std::string username() const;
    PN_CPP_EXTERN std::string password() const;
    PN_CPP_EXTERN std::string host() const;
    /** port is a string, it can be a number or a symbolic name like "amqp" */
    PN_CPP_EXTERN std::string port() const;
    PN_CPP_EXTERN std::string path() const;
    //@}

    /** host_port returns just the host:port part of the URL */
    PN_CPP_EXTERN std::string host_port() const;

    /**@name Set parts of the URL
     *@{
     */
    PN_CPP_EXTERN void scheme(const std::string&);
    PN_CPP_EXTERN void username(const std::string&);
    PN_CPP_EXTERN void password(const std::string&);
    PN_CPP_EXTERN void host(const std::string&);
    /** port is a string, it can be a number or a symbolic name like "amqp" */
    PN_CPP_EXTERN void port(const std::string&);
    PN_CPP_EXTERN void path(const std::string&);
    //@}

    /** defaults fills in default values for missing parts of the URL */
    PN_CPP_EXTERN void defaults();

  private:
    pn_url_t* url_;
};

std::ostream& operator<<(std::ostream&, const url&);
}

#endif // URL_HPP
